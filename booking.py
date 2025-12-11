# app.py
import streamlit as st
from PIL import Image
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import base64
import pytz

# ===================== CONFIG =====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Change this if your studio is not in Miami
STUDIO_TZ = pytz.timezone("America/New_York")

# Stripe from secrets
if st.secrets.get("STRIPE_SECRET_KEY"):
    stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")
SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/")
CANCEL_URL = st.secrets.get("STRIPE_CANCEL_URL", "https://your-app.streamlit.app/")

# ===================== DATABASE =====================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
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
        deposit_paid INTEGER DEFAULT 0,
        stripe_session_id TEXT,
        files TEXT,
        created_at TEXT
    )
""")
conn.commit()

# ===================== ICS GENERATOR =====================
def create_ics(uid, title, desc, start_dt, end_dt, org_mail, attendee_mail):
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%SZ")
    dtend = end_dt.strftime("%Y%m%dT%H%M%SZ")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Cashin Ink//EN
BEGIN:VEVENT
UID:{uid
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{title}
DESCRIPTION:{desc}
ORGANIZER;CN=Cashin Ink:mailto:{org_mail}
ATTENDEE;CN=Client;RSVP=TRUE:mailto:{attendee_mail}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
    return ics.strip().encode("utf-8")

# ===================== CONFLICT CHECK =====================
def slot_taken(start_utc, end_utc, exclude_id=None):
    query = "SELECT 1 FROM bookings WHERE deposit_paid = 1 AND id != ? AND start_dt < ? AND end_dt > ?"
    return c.execute(query, (exclude_id or "", end_utc.isoformat(), start_utc.isoformat())).fetchone() is not None

# ===================== PAGE STYLE =====================
st.set_page_config(page_title="Cashin Ink — Book Now", layout="centered", page_icon="Tattoo Needle")

st.markdown("""
<style>
    .stApp { background: #000; color: white; }
    .block-container { padding-top: 1rem; }
    h1, h2, h3 { color: #00C853 !important; }
    .stButton>button { background: #00C853; color: black; font-weight: bold; border: none; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background: #111; color: white; }
</style>
""", unsafe_allow_html=True)

# ===================== HEADER WITH LOGO & BG =====================
col1, col2 = st.columns([1, 5])
with col1:
    if os.path.exists("B57CEC91-3B05-4094-97F4-ED1C90DA0B9D.jpeg"):
        st.image("B57CEC91-3B05-4094-97F4-ED1C90DA0B9D.jpeg", width=110)
with col2:
    st.markdown("<h1 style='margin:0; color:#00C853'>CASHIN INK</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0; color:#aaa'>Julio Munoz • Miami</p>", unsafe_allow_html=True)

if os.path.exists("A5B0F3EA-FEAE-40AD-ACE9-9182CBA69EE0.jpeg"):
    st.image("A5B0F3EA-FEAE-40AD-ACE9-9182CBA69EE0.jpeg", use_column_width=True)

st.markdown("---")

# ===================== BOOKING FORM =====================
st.header("Book Your Appointment — $150 Deposit Required")

with st.form("booking"):
    st.write("**Your Info**")
    c1, c2 = st.columns(2)
    name = c1.text_input("Full Name*")
    age = c2.number_input("Age*", 18, 100)
    phone = c1.text_input("Phone*")
    email = c2.text_input("Email*")
    description = st.text_area("What do you want? (size, placement, style, ideas)*", height=100)

    st.write("**Reference Images (highly recommended)**")
    uploaded = st.file_uploader("Upload photos, drawings, PDFs...", accept_multiple_files=True,
                                type=['png','jpg','jpeg','heic','pdf'], label_visibility="collapsed")

    st.markdown("---")
    st.write("**Pick Your Day & Time**")
    date = st.date_input("Date", min_value=datetime.today() + timedelta(days=1))
    time = st.time_input("Start Time", value=datetime.strptime("13:00", "%H:%M").time())

    agree = st.checkbox("I am 18+ and agree to the non-refundable $150 deposit policy*")
    submit = st.form_submit_button("Pay $150 Deposit → Lock My Slot")

    if submit:
        if not all([name, phone, email, description]):
            st.error("Fill all required fields")
        elif age < 18:
            st.error("Must be 18+")
        elif not agree:
            st.error("You must agree to the deposit policy")
        else:
            # Fixed 2-hour appointment (2 hours
            naive_start = datetime.combine(date, time)
            local_start = STUDIO_TZ.localize(naive_start)
            local_end = local_start + timedelta(hours=2)
            utc_start = local_start.astimezone(pytz.UTC)
            utc_end = local_end.astimezone(pytz.UTC)

            if slot_taken(utc_start, utc_end):
                st.error("That time just got taken! Please pick another.")
                st.stop()

            booking_id = str(uuid.uuid4())

            # Save files
            saved = []
            if uploaded:
                dir_path = os.path.join(UPLOAD_DIR, booking_id)
                os.makedirs(dir_path, exist_ok=True)
                for f in uploaded:
                    path = os.path.join(dir_path, f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    saved.append(path)

            # Create Stripe session
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {'name': f'Deposit – {name} – {date}'},
                            'unit_amount': 15000,
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=SUCCESS_URL + f"?booking_id={booking_id}",
                    cancel_url=CANCEL_URL,
                    metadata={'booking_id': booking_id},
                )

                # Save provisional booking
                c.execute("""INSERT INTO bookings 
                    (id, name, age, phone, email, description, date, time, start_dt, end_dt,
                     deposit_paid, stripe_session_id, files, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (booking_id, name, age, phone, email, description,
                     str(date), str(time), utc_start.isoformat(), utc_end.isoformat(),
                     0, session.id, ",".join(saved), datetime.utcnow().isoformat()))
                conn.commit()

                st.success("Taking you to secure payment...")
                st.markdown(f"[Click if not redirected →]({session.url})")
                st.markdown(f"<meta http-equiv='refresh' content='2;url={session.url}'>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Payment setup failed: {e}")

st.markdown("---")
st.header("My Bookings")

rows = c.execute("""SELECT id, name, date, time, deposit_paid, start_dt, end_dt, email, files 
                    FROM bookings ORDER BY date, time""").fetchall()

if rows:
    for row in rows:
        bid, name, date, time, paid, sdt, edt, email, files = row
        status = "PAID – LOCKED" if paid else "Pending payment"
        color = "#00C853" if paid else "#FF5722"
        st.markdown(f"**{name}** — {date} at {time} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

        if paid and sdt:
            try:
                start = datetime.fromisoformat(sdt).astimezone(STUDIO_TZ)
                end = datetime.fromisoformat(edt).astimezone(STUDIO_TZ)
                ics = create_ics(f"{bid}@cashinink", f"Cashin Ink – {name}", description, start, end, ORGANIZER_EMAIL, email)
                b64 = base64.b64encode(ics).decode()
                st.markdown(f"Download .ics → Add to Calendar](data:text/calendar;base64,{b64})", unsafe_allow_html=True)
            except:
                pass
else:
    st.info("No bookings yet.")

# ===================== SUCCESS PAGE =====================
params = st.experimental_get_query_params()
if "booking_id" in params:
    bid = params["booking_id"][0]
    row = c.execute("SELECT name, email, start_dt, end_dt FROM bookings WHERE id=?", (bid,)).fetchone()
    if row:
        name, email, sdt, edt = row
        # Mark as paid using Stripe session (more reliable than URL param alone)
        if stripe.api_key:
            rec = c.execute("SELECT stripe_session_id FROM bookings WHERE id=?", (bid,)).fetchone()
            if rec and rec[0]:
                session = stripe.checkout.Session.retrieve(rec[0])
                if session.payment_status == "paid":
                    c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
                    conn.commit()
                    st.balloons()
                    st.success(f"Payment confirmed! Your spot on {sdt[:10]} is 100% locked.")
                    start = datetime.fromisoformat(sdt).astimezone(STUDIO_TZ)
                    end = datetime.fromisoformat(edt).astimezone(STUDIO_TZ)
                    ics = create_ics(f"{bid}@cashinink", f"Cashin Ink – {name}", "", start, end, ORGANIZER_EMAIL, email)
                    b64 = base64.b64encode(ics).decode()
                    st.markdown(f"### Add to Calendar](data:text/calendar;base64,{b64})", unsafe_allow_html=True)

st.markdown("---")
st.caption("Cashin Ink © 2025 • Julio Munoz • All deposits non-refundable")