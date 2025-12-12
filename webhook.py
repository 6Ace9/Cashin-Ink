# webhook.py — DEPLOY THIS ON RAILWAY (or Render/Fly.io)
# This file does ALL the magic: marks paid + adds to Apple Calendar instantly

from flask import Flask, request, jsonify
import stripe
import sqlite3
import os
import pytz
from datetime import datetime
import caldav

app = Flask(__name__)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

DB_PATH = "bookings.db"  # Will be mounted as volume in Railway
STUDIO_TZ = pytz.timezone("America/New_York")

# Apple Calendar
client = caldav.DAVClient(
    url="https://caldav.icloud.com",
    username=os.environ["ICLOUD_USER"],
    password=os.environ["ICLOUD_PASS"]  # App-Specific Password
)
calendar = client.principal().calendars()[0]

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def add_to_calendar(name, desc, start_dt, end_dt):
    event = f"""
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Tattoo Session - {name}
DESCRIPTION:{desc}
DTSTART:{start_dt.astimezone(pytz.UTC).strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end_dt.astimezone(pytz.UTC).strftime('%Y%m%dT%H%M%SZ')}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
 """.strip()
 calendar.add_event(event)

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except:
        return jsonify(success=False), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        booking_id = session.metadata.get("booking_id")
        if not booking_id:
            return jsonify(success=True), 200

        row = c.execute("SELECT deposit_paid, name, description, start_dt, end_dt FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if row and row[0] == 0:
            c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (booking_id,))
            conn.commit()

            name, desc, s, e = row[1], row[2], row[3], row[4]
            start_dt = datetime.fromisoformat(s).astimezone(STUDIO_TZ)
            end_dt = datetime.fromisoformat(e).astimezone(STUDIO_TZ)

            try:
                add_to_calendar(name, desc, start_dt, end_dt)
                print(f"Added: {name} – {start_dt.strftime('%b %d %I:%M %p')}")
            except Exception as e:
                print("Calendar failed:", e)

    return jsonify(success=True), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
