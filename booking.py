# app.py ← REPLACE YOUR ENTIRE FILE WITH THIS
import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import base64
import pytz

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")

stripe.api_key = st.secrets.get("STRIPE_SECRET_KEY")
SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/")
CANCEL_URL  = st.secrets.get("STRIPE_CANCEL_URL",  "https://your-app.streamlit.app/")
ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")

# ==================== DATABASE ====================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''
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
''')
conn.commit()

# ==================== ICS ====================
def create_ics(uid, title, desc, start_dt, end_dt):
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Cashin Ink//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}
DTSTART:{start_dt:%Y%m%dT%H%M%SZ}
DTEND:{end_dt:%Y%m%dT%H%M%SZ}
SUMMARY:{title}
DESCRIPTION:{desc}
ORGANIZER;CN=Cashin Ink:mailto:{ORGANIZER_EMAIL}
ATTENDEE;CN=Client;RSVP=TRUE:mailto:{desc.split()[-1] if desc else ""}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR""".strip().encode("utf-8")

# ==================== CONFLICT CHECK ====================
def slot_taken(start_utc, end_utc):
    row = c.execute("SELECT 1 FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                    (end_utc.isoformat(), start_utc.isoformat())).fetchone()
    return row is not None

# ==================== FORCE 12-HOUR FORMAT IN STREAMLIT ====================
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")
st.markdown("""
<style>
    .stApp { background:#000; color:#fff; }
    h1,h2,h3 { color:#00C853 !important; }
    .stButton>button { background:#00C853; color:black; font-weight:bold; border:none; }
    /* THIS LINE FORCES 12-HOUR TIME EVERYWHERE */
    [data-testid="stTimeInput"] input { format: "h:mm A" !important; }
</style>
""", unsafe_allow_html=True)

# ==================== HEADER ====================
col1, col2 = st.columns([1,5])
with col1:
    if os.path.exists("Untitled_Artwork.png"):
        st.image("Untitled_Artwork.png", width=130)
with col2:
    st.markdown("<h1 style='margin:0;color:#00C853'>CASHIN INK</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0;color:#aaa'>Julio Munoz • Miamip>", unsafe_allow_html=True)

if os.path.exists("IMG_6745.png"):
    st.image("IMG_6745.png", use_column_width=True)

st.markdown("---")

# ==================== BOOKING FORM ====================
st.header("Book Your Tattoo — $150 Deposit Required")
st.info("2-hour session • Deposit locks your spot")

with st.form("booking_form"):
    name  = st.text_input("Full Name*")
    age   = st.number_input("Age*", 18, 100, 18)
    phone = st.text_input("Phone*")
    email = st.text_input("Email*")
    description = st.text_area("Tattoo idea (size, placement, style)*", height=100)

    st.file_uploader("Reference photos/sketches", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)

    st.markdown("---")
    appt_date = st.date_input("Date", min_value=datetime.today() + timedelta(days=1))

    # THIS IS THE MAGIC LINE — 12-hour clock with AM/PM
    appt_time = st.time_input(
        "Start Time",
        value=datetime.strptime("1:00 PM", "%I:%M %p").time(),
        step=timedelta(minutes=30)
    )

    agree = st.checkbox("I am 18+ and agree to the $150 non-refundable deposit*")
    submit = st.form_submit_button("Pay $150 Deposit → Lock My Spot")

    if submit:
        if not all([name, phone, email, description]):
            st.error("Fill all fields")
        elif age < 18:
            st.error("Must be 18+")
        elif not agree:
            st.error("Accept the deposit policy")
        else:
            local_start = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            local_end   = local_start + timedelta(hours=2)
            utc_start   = local_start.astimezone(pytz.UTC)
            utc_end     = local_end.astimezone(pytz.UTC)

            if slot_taken(utc_start, utc_end):
                st.error("Slot just taken — pick another time!")
                st.stop()

            booking_id = str(uuid.uuid4())
            folder = os.path.join(UPLOAD_DIR, booking_id)
            os.makedirs(folder, exist_ok=True)
            saved = [os.path.join(folder, f.name) for f in st.session_state.get("uploaded_files", [])]
            for f in st.session_state.get("uploaded_files", []):
                with open(os.path.join(folder, f.name), "wb") as out:
                    out.write(f.getbuffer())

            # SAVE TIME AS "3:30 PM" — NEVER 15:30
            pretty_time = appt_time.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price_data": {"currency": "usd", "product_data": {"name": f"Deposit – {name}"}, "unit_amount": 15000}, "quantity": 1}],
                mode="payment",
                success_url=SUCCESS_URL + f"?booking_id={booking_id}",
                cancel_url=CANCEL_URL,
                metadata={"booking_id": booking_id},
            )

            c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                booking_id, name, age, phone, email, description,
                str(appt_date), pretty_time, utc_start.isoformat(), utc_end.isoformat(),
                0, session.id, ",".join(saved), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Taking you to payment...")
            st.markdown(f"<meta http-equiv='refresh' content='2;url={session.url}'>", unsafe_allow_html=True)
            st.markdown(f"[Click here →]({session.url})")

# ==================== SHOW BOOKINGS (12-hour time) ====================
st.markdown("---")
st.header("Upcoming Appointments")

for row in c.execute("SELECT name,date,time,deposit_paid FROM bookings ORDER BY date,time").fetchall():
    name, date, time, paid = row
    status = "PAID" if paid else "Pending"
    color = "#00C853" if paid else "#FF5722"
    st.markdown(f"**{name}** — {date} at **{time}** — <span style='color:{color}'>{status}span>", unsafe_allow_html=True)

# Success page
if st.query_params.get("booking_id"):
    bid = st.query_params["booking_id"]
    row = c.execute("SELECT name,time FROM bookings WHERE id=?", (bid,)).fetchone()
    if row:
        name, time = row
        c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
        conn.commit()
        st.balloons()
        st.success(f"DEPOSIT CONFIRMED! See you {name} on your date at {time}")

st.markdown("---")
st.caption("© 2025 Cashin Ink • Julio Munoz • Miami")