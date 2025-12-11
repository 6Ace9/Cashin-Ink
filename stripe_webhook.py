# stripe_webhook.py
import os
import json
import sqlite3
from datetime import datetime
import pytz
import stripe
from flask import Flask, request, jsonify
import caldav
from caldav.elements import dav

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
STUDIO_TZ = pytz.timezone("America/New_York")

# Stripe webhook secret (set in your Stripe dashboard)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# Apple Calendar credentials (Julio)
ICLOUD_USER = os.environ.get("ICLOUD_USER")
ICLOUD_PASS = os.environ.get("ICLOUD_PASS")

# Connect to Apple Calendar
cal_client = caldav.DAVClient(
    url="https://caldav.icloud.com/",
    username=ICLOUD_USER,
    password=ICLOUD_PASS
)
principal = cal_client.principal()
JULIO_CALENDAR = principal.calendars()[0]  # default calendar

# Connect to SQLite
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ==================== APPLE CALENDAR FUNCTION ====================
def create_apple_event(name, description, start_dt, end_dt):
    start_utc = start_dt.astimezone(pytz.UTC)
    end_utc = end_dt.astimezone(pytz.UTC)
    event_data = f"""
    BEGIN:VCALENDAR
    VERSION:2.0
    BEGIN:VEVENT
    SUMMARY:Tattoo Appointment - {name}
    DESCRIPTION:{description}
    DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}
    DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}
    END:VEVENT
    END:VCALENDAR
    """
    JULIO_CALENDAR.add_event(event_data)

# ==================== FLASK APP ====================
app = Flask(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

@app.route("/webhook", methods=["POST"])
def webhook_received():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return jsonify(success=False), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return jsonify(success=False), 400

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        booking_id = session["metadata"]["booking_id"]

        # Mark deposit_paid = 1 in database
        row = c.execute(
            "SELECT name, description, start_dt, end_dt FROM bookings WHERE id=?",
            (booking_id,)
        ).fetchone()

        if row:
            name, description, start_iso, end_iso = row
            c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (booking_id,))
            conn.commit()

            # Add to Apple Calendar
            try:
                local_start = datetime.fromisoformat(start_iso).astimezone(STUDIO_TZ)
                local_end   = datetime.fromisoformat(end_iso).astimezone(STUDIO_TZ)
                create_apple_event(name, description, local_start, local_end)
                print(f"Added booking {name} to Apple Calendar")
            except Exception as e:
                print(f"Failed to add booking to Apple Calendar: {e}")

    return jsonify(success=True), 200

if __name__ == "__main__":
    # Run on localhost for testing: curl -X POST http://127.0.0.1:5000/webhook
    app.run(port=5000)
