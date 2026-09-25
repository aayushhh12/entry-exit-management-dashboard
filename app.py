"""
Hackathon Attendance Dashboard — backend
-----------------------------------------
Handles:
  - Logging QR scan events to a Google Sheet
  - Computing live status (In / On Break / Out) per participant
  - Manual regularization (edit/add a log entry)
  - A chat endpoint that answers questions about the data using Gemini (free tier)

Run with:  python app.py
Then open: http://localhost:5000/dashboard  and  http://localhost:5000/scan
"""

import os
import datetime
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

app = Flask(__name__)

# ---------- Google Sheets setup ----------

def get_sheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = sh.worksheet("Log")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Log", rows=1000, cols=4)
        ws.append_row(["Timestamp", "ParticipantID", "Name", "EventType"])
    return ws


# The valid event sequence per participant, in order.
EVENT_SEQUENCE = ["Entry", "Break Out", "Break In", "Exit"]


def next_expected_event(last_event):
    """Given a participant's last event, figure out the sensible next one."""
    if last_event is None or last_event == "Exit":
        return "Entry"
    if last_event == "Entry":
        return "Break Out"  # could also be Exit; scan page lets them pick if needed
    if last_event == "Break Out":
        return "Break In"
    if last_event == "Break In":
        return "Break Out"
    return "Entry"


def get_all_records():
    ws = get_sheet()
    return ws.get_all_records()  # list of dicts, one per row


def compute_statuses(records):
    """Turn raw event rows into a per-participant summary."""
    people = {}
    for row in records:
        pid = str(row.get("ParticipantID", "")).strip()
        if not pid:
            continue
        people.setdefault(pid, {"name": row.get("Name", ""), "events": []})
        people[pid]["events"].append(
            {"type": row.get("EventType"), "time": row.get("Timestamp")}
        )

    summary = []
    for pid, info in people.items():
        events = sorted(info["events"], key=lambda e: e["time"])
        status = "Not checked in"
        entry_time = None
        exit_time = None
        break_seconds = 0
        last_break_start = None

        for e in events:
            t = e["type"]
            ts = e["time"]
            if t == "Entry":
                status = "In"
                entry_time = entry_time or ts
            elif t == "Break Out":
                status = "On Break"
                last_break_start = ts
            elif t == "Break In":
                status = "In"
                if last_break_start:
                    try:
                        fmt = "%Y-%m-%d %H:%M:%S"
                        delta = (
                            datetime.datetime.strptime(ts, fmt)
                            - datetime.datetime.strptime(last_break_start, fmt)
                        ).total_seconds()
                        break_seconds += max(delta, 0)
                    except Exception:
                        pass
                    last_break_start = None
            elif t == "Exit":
                status = "Out"
                exit_time = ts

        summary.append(
            {
                "participant_id": pid,
                "name": info["name"],
                "status": status,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "break_minutes": round(break_seconds / 60, 1),
            }
        )
    return summary


# ---------- Routes: pages ----------

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/scan")
def scan_page():
    return render_template("scan.html")


# ---------- Routes: API ----------

@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Called by the scan page after a QR code is read."""
    data = request.json
    pid = str(data.get("participant_id", "")).strip()
    name = data.get("name", "")
    override_event = data.get("event_type")  # optional manual override

    if not pid:
        return jsonify({"error": "Missing participant_id"}), 400

    records = get_all_records()
    my_events = [r for r in records if str(r.get("ParticipantID")) == pid]
    last_event = my_events[-1]["EventType"] if my_events else None

    event_type = override_event or next_expected_event(last_event)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ws = get_sheet()
    ws.append_row([timestamp, pid, name, event_type])

    return jsonify({"logged": event_type, "timestamp": timestamp})


@app.route("/api/status")
def api_status():
    records = get_all_records()
    return jsonify(compute_statuses(records))


@app.route("/api/regularize", methods=["POST"])
def api_regularize():
    """Admin: manually add a corrected log entry."""
    data = request.json
    pid = str(data.get("participant_id", "")).strip()
    name = data.get("name", "")
    event_type = data.get("event_type")
    timestamp = data.get("timestamp") or datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if not pid or not event_type:
        return jsonify({"error": "participant_id and event_type are required"}), 400

    ws = get_sheet()
    ws.append_row([timestamp, pid, name, event_type])
    return jsonify({"ok": True})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """Ask a natural-language question about today's attendance data."""
    question = request.json.get("question", "")
    if not question:
        return jsonify({"error": "Missing question"}), 400

    records = get_all_records()
    summary = compute_statuses(records)

    # Keep the context compact — send the computed summary, not raw rows.
    context_lines = [
        f"{p['name']} (ID {p['participant_id']}): status={p['status']}, "
        f"entry={p['entry_time']}, exit={p['exit_time']}, "
        f"break_minutes={p['break_minutes']}"
        for p in summary
    ]
    context = "\n".join(context_lines) if context_lines else "No attendance data yet."

    prompt = (
        "You are an assistant answering questions about hackathon attendance data. "
        "Here is today's data, one participant per line:\n\n"
        f"{context}\n\n"
        f"Question: {question}\n"
        "Answer concisely based only on the data above."
    )

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}]
            },
            timeout=30,
        )
        resp.raise_for_status()
        answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return jsonify({"error": f"Gemini request failed: {e}"}), 500

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
