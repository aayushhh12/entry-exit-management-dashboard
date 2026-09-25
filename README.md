# Hackathon Attendance Dashboard

Tracks Entry → Break Out → Break In → Exit for each participant via QR scan,
stores everything in a Google Sheet, shows a live dashboard, supports manual
regularization, and lets you ask questions about the data using Gemini (free tier).

## 1. Install dependencies

```
cd hackathon-dashboard
pip install -r requirements.txt
```

## 2. Set up the Google Sheet

1. Go to https://sheets.google.com and create a new blank spreadsheet.
   Name it anything (e.g. "Hackathon Attendance").
2. Copy the Sheet ID from its URL:
   `https://docs.google.com/spreadsheets/d/1-aDifJd4ozNJ6pOjrg3Yx9ulA-eHlNU2AD_LlOV2wGA/edit`
3. You do NOT need to add headers manually — the app creates a "Log" tab
   with headers automatically on first run.

## 3. Create a Google Service Account (so the app can write to your Sheet)

1. Go to https://console.cloud.google.com/ and create a new project (or use an existing one).
2. Enable the **Google Sheets API** for that project (search for it in "APIs & Services" → "Library").
3. Go to "APIs & Services" → "Credentials" → "Create Credentials" → "Service Account".
4. Give it any name, finish creation.
5. Open the new service account → "Keys" tab → "Add Key" → "Create new key" → JSON.
   This downloads a `.json` file — rename it to `service_account.json` and put it
   in this project folder.
6. Open the JSON file and copy the `client_email` value (looks like
   `something@your-project.iam.gserviceaccount.com`).
7. Go back to your Google Sheet → click "Share" → paste that email in →
   give it "Editor" access → Share.

This lets the app read/write your Sheet without ever using your personal Google login.

## 4. Get a free Gemini API key

1. Go to https://aistudio.google.com/apikey (Google AI Studio).
2. Sign in with a Google account, click "Create API key".
3. Copy the key — this is your `GEMINI_API_KEY`. It's free with generous
   rate limits (no card required for the free tier).

## 5. Set up your .env file

Copy `.env.example` to `.env` and fill in:

```
GEMINI_API_KEY=your real Gemini key
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_SHEET_ID=the sheet ID from step 2
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
```

## 6. Generate QR codes for participants

Edit the `participants` list in `generate_qr_codes.py`, then run:

```
python generate_qr_codes.py
```

This creates a `qr_codes/` folder with one PNG per person. Print these or
display them on a screen at the check-in desk.

## 7. Run the app

```
python app.py
```

Then open in a browser:
- **Scan page** (for the check-in desk / a tablet): http://localhost:5000/scan
- **Dashboard** (for organizers to watch live): http://localhost:5000/dashboard

## How the check-in logic works

Each scan looks at that participant's last logged event and figures out the
sensible next step automatically:

```
(none) → Entry → Break Out → Break In → Break Out → ... → Exit
```

So people just scan their code each time they leave their seat or the venue —
no need to pick "which button" themselves.

## Regularization

If someone forgot to scan (e.g., missed tapping "Break In"), an organizer can
open the dashboard, go to the "Regularize an entry" section, and manually add
the correct event with the right timestamp. This appends directly to the
Google Sheet log, and the dashboard recalculates automatically.

## The Gemini chat box

Type things like:
- "Who is currently on a break?"
- "How many people have left already?"
- "Who has taken the longest total break time?"

The backend sends a compact summary of the day's data (not the raw sheet) to
Gemini's `gemini-2.5-flash` model and returns the answer. Your API key stays
on the server — it's never sent to the browser.

Note: on Gemini's free tier, Google may use your prompts to improve their
products — fine for testing, but avoid sending sensitive personal data if
that matters for your event.

## Notes / next steps

- This is a starting point, not a production system. For a real hackathon,
  consider: authentication on the dashboard, rate-limiting scans, backing up
  the sheet periodically, and testing the QR flow with a few people before
  the event.
- If you'd rather run this entirely on your own machine hands-on with live
  debugging, Claude Code (which you already installed) is a great place to
  keep iterating on this — just point it at this folder.
