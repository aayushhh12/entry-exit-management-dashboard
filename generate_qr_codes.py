"""
Generates one QR code image per participant.
Edit the `participants` list below, then run: python generate_qr_codes.py
QR codes are saved into the qr_codes/ folder as <ID>.png — print or display these
for people to scan at check-in.
"""

import json
import os
import qrcode

participants = [
    {"id": "P001", "name": "Aayush Kothari"},
    {"id": "P002", "name": "Ridhi Batra"},
    {"id": "P003", "name": "Akshat Goud"},
    {"id": "P004", "name": "Rahim Khan"},
    # Add more participants here
]

os.makedirs("qr_codes", exist_ok=True)

for p in participants:
    payload = json.dumps({"id": p["id"], "name": p["name"]})
    img = qrcode.make(payload)
    path = f"qr_codes/{p['id']}.png"
    img.save(path)
    print(f"Saved {path}")
