# stripe_webhook.py — RUN THIS SEPARATELY FROM STREAMLIT APP
from flask import Flask, request, jsonify
import stripe
import sqlite3
import os
import pytz
from datetime import datetime
import caldav

app = Flask(__name__)

# ==================== CONFIG ====================
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

DB_PATH = "bookings.db"  # Same DB as Streamlit (shared volume or copy)

STUDIO_TZ = pytz.timezone("America/New_York")

# iCloud CalDAV (use App-Specific Password!)
cal_client = caldav.DAVClient(
    url="https://caldav.icloud.com",
    username=os.environ["ICLOUD_USER"],
    password=os.environ["ICLOUD_PASS"]  # ← App-Specific Password
)
principal = cal_client.principal()
calendar = principal.calendars()[0]

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def add_to_apple_calendar(name, desc, start_dt, end_dt):
    event = f"""
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Tattoo - {name}
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
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Webhook signature failed:", e)
        return jsonify(success=False), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        booking_id = session.get("metadata", {}).get("booking_id")

        if not booking_id:
            return jsonify(success=True), 200

        row = c.execute(
            "SELECT name, description, start_dt, end_dt FROM bookings WHERE id=?",
            (booking_id,)
        ).fetchone()

        if row and not c.execute("SELECT deposit_paid FROM bookings WHERE id=?", (booking_id,)).fetchone()[0]:
            name, desc, start_iso, end_iso = row
            c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (booking_id,))
            conn.commit()

            try:
                start_dt = datetime.fromisoformat(start_iso).astimezone(STUDIO_TZ)
                end_dt = datetime.fromisoformat(end_iso).astimezone(STUDIO_TZ)
                add_to_apple_calendar(name, desc, start_dt, end_dt)
                print(f"Added to calendar: {name} on {start_dt.strftime('%b %d %I:%M %p')}")
            except Exception as e:
                print("Calendar sync failed:", e)

    return jsonify(success=True), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))