# app.py
import streamlit as st
from PIL import Image
import sqlite3
import os
import stripe
from io import BytesIO
from datetime import datetime, timedelta
import uuid
import base64
import pytz
import pandas as pd
import hashlib

# ===================== CONFIG =====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Timezone for the studio (change if needed)
STUDIO_TZ = pytz.timezone("America/New_York")

# Stripe
stripe.api_key = st.secrets.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = st.secrets.get("STRIPE_WEBHOOK_SECRET", "")

# Emails
ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")

# ===================== DATABASE =====================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute(
    """CREATE TABLE IF NOT EXISTS bookings (
        id TEXT PRIMARY KEY,
        name TEXT,
        age INTEGER,
        phone TEXT,
        email TEXT,
        description TEXT,
        date TEXT,
        time TEXT,
        start_dt TEXT,
        end_dt TEXT,
        duration_hours REAL,
        deposit_paid INTEGER DEFAULT 0,
        stripe_session_id TEXT,
        files TEXT,
        created_at TEXT
    )"""
)
conn.commit()

# ===================== ICS GENERATOR =====================
def create_ics(uid, title, description, start_dt, end_dt, organizer_email, attendee_email):
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%SZ")
    dtend = end_dt.strftime("%Y%m%dT%H%M%SZ")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Cashin Ink//Booking//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{title}
DESCRIPTION:{description}
ORGANIZER;CN=Cashin Ink:mailto:{organizer_email}
ATTENDEE;CN=Client;RSVP=TRUE;PARTSTAT=NEEDS-ACTION:mailto:{attendee_email}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""
    return ics.strip().encode('utf-8')

# ===================== CONFLICT CHECKER =====================
def has_conflict(start_dt_utc, end_dt_utc, exclude_id=None):
    query = "SELECT 1 FROM bookings WHERE deposit_paid = 1 AND id != ? AND (start_dt < ? AND end_dt > ?)"
    params = (exclude_id or "", end_dt_utc.isoformat(), start_dt_utc.isoformat())
    return c.execute(query, params).fetchone() is not None

# ===================== PAGE SETUP =====================
st.set_page_config(page_title="Cashin Ink — Book Now", layout="centered", page_icon="💉")

st.markdown(
    """
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    .block-container { padding-top: 1rem; }
    h1, h2, h3 { color: #00C853 !important; }
    .stButton>button {
        background: linear-gradient(90deg,#00C853,#00E676);
        color: black !important;
        font-weight: bold;
        border: none;
        border-radius: 8px;
    }
    .stTextInput>div>input, .stTextArea>div>textarea {
        background: #111111; color: #fff; border-radius: 6px;
    }
    .upload-box { border: 2px dashed #00C853; padding: 20px; border-radius: 12px; text-align: center; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
col1, col2 = st.columns([1, 4])
with col1:
    if os.path.exists("B57CEC91-3B05-4094-97F4-ED1C90DA0B9D.jpeg"):
        st.image("B57CEC91-3B05-4094-97F4-ED1C90DA0B9D.jpeg", width=120)
with col2:
    st.markdown("<h1 style='margin:0;color:#00C853'>CASHIN INK</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#888;margin:0'>Owner: Julio Munoz</p>", unsafe_allow_html=True)

if os.path.exists("A5B0F3EA-FEAE-40AD-ACE9-9182CBA69EE0.jpeg"):
    st.image("A5B0F3EA-FEAE-40AD-ACE9-9182CBA69EE0.jpeg", use_column_width=True)

st.markdown("---")

# ===================== BOOKING FORM =====================
st.header("Book Your Tattoo — $150 Deposit Required")
st.info("All appointments require a **non-refundable $150 deposit** to lock your slot. This goes toward your final tattoo price.")

with st.form("booking_form"):
    st.subheader("Your Info")
    c1, c2 = st.columns(2)
    name = c1.text_input("Full Name*")
    age = c2.number_input("Age*", min_value=14, max_value=100, value=18)
    phone = c1.text_input("Phone*")
    email = c2.text_input("Email*")

    description = st.text_area("Tattoo Idea* (style, size, placement, reference ideas)", height=120)

    st.markdown("**Upload Reference Images / Drawings (optional but recommended)**")
    uploaded_files = st.file_uploader("Photos, sketches, PDFs", accept_multiple_files=True,
                                      type=['png','jpg','jpeg','heic','pdf','mp4'], label_visibility="collapsed")

    st.markdown("---")
    st.subheader("Pick Date & Time")
    appt_date = st.date_input("Date", min_value=datetime.today().date() + timedelta(days=1))
    appt_time = st.time_input("Start Time", value=datetime.strptime("12:00", "%H:%M").time())
    duration_hours = st.selectbox("Estimated Duration", [1.5, 2, 2.5, 3, 4, 5, 6], index=1)

    agree = st.checkbox("I am 18+ and agree to Cashin Ink's deposit & cancellation policy")

    submitted = st.form_submit_button("Pay $150 Deposit → Lock My Spot")

    if submitted:
        if not all([name, phone, email, description]):
            st.error("Please fill in all required fields.")
        elif age < 18:
            st.error("Must be 18 or older.")
        elif not agree:
            st.error("You must agree to the policy.")
        else:
            # Convert to aware datetime in studio timezone
            naive_start = datetime.combine(appt_date, appt_time)
            local_start = STUDIO_TZ.localize(naive_start)
            local_end = local_start + timedelta(hours=duration_hours)
            utc_start = local_start.astimezone(pytz.UTC)
            utc_end = local_end.astimezone(pytz.UTC)

            # Check conflict
            if has_conflict(utc_start, utc_end):
                st.error("That time slot is no longer available. Please choose another.")
                st.stop()

            booking_id = str(uuid.uuid4())

            # Save files
            saved_paths = []
            if uploaded_files = ""
            if uploaded_files:
                booking_dir = os.path.join(UPLOAD_DIR, booking_id)
                os.makedirs(booking_dir, exist_ok=True)
                for file in uploaded_files:
                    path = os.path.join(booking_dir, file.name)
                    with open(path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_paths.append(path)
                saved_files = ",".join(saved_paths)

            # Create Stripe Checkout Session
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': f'Tattoo Deposit – {name} – {appt_date}',
                            },
                            'unit_amount': 15000,
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=st.secrets["STRIPE_SUCCESS_URL"] + f"?booking_id={booking_id}",
                    cancel_url=st.secrets["STRIPE_CANCEL_URL"],
                    metadata={
                        'booking_id': booking_id,
                        'client_name': name,
                        'client_email': email,
                    },
                    client_reference_id=booking_id,
                )

                # Save provisional booking
                c.execute("""INSERT INTO bookings 
                    (id, name, age, phone, email, description, date, time, start_dt, end_dt, duration_hours,
                     deposit_paid, stripe_session_id, files, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ,
                    (booking_id, name, age, phone, email, description,
                     str(appt_date), str(appt_time), utc_start.isoformat(), utc_end.isoformat(),
                     duration_hours, 0, session.id, saved_files, datetime.utcnow().isoformat())
                )
                conn.commit()

                st.success("Redirecting to secure payment...")
                st.markdown(f"<meta http-equiv='refresh' content='2;url={session.url}'>", unsafe_allow_html=True)
                st.markdown(f"[Click here if not redirected →]({session.url})")

            except Exception as e:
                st.error(f"Payment error: {e}")

# ===================== MY BOOKINGS =====================
st.markdown("---")
st.header("My Bookings")

rows = c.execute("""SELECT id, name, date, time, deposit_paid, start_dt, end​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​​