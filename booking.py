# app.py  (or booking.py — name doesn't matter)
import streamlit as st
from PIL import Image
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

STUDIO_TZ = pytz.timezone("America/New_York")  # Miami time

# Secrets (add these in Streamlit → Settings → Secrets)
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

# ==================== ICS GENERATOR ====================
def create_ics(uid, title, desc, start_dt, end_dt, org_mail, attendee_mail):
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%SZ")
    dtend   = end_dt.strftime("%Y%m%dT%H%M%SZ")
    
    ics_content = f"""BEGIN:VCALENDAR
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
DESCRIPTION:{desc}
ORGANIZER;CN=Cashin Ink:mailto:{org_mail}
ATTENDEE;CN=Client;RSVP=TRUE:mailto:{attendee_mail}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
    return ics_content.strip().encode("utf-8")

# ==================== CONFLICT CHECK ====================
def slot_taken(start_utc, end_utc, exclude_id=None):
    row = c.execute("""
        SELECT 1 FROM bookings 
        WHERE deposit_paid = 1 
          AND id != ? 
          AND start_dt < ? 
          AND end_dt > ?
    """, (exclude_id or "", end_utc.isoformat(), start_utc.isoformat())).fetchone()
    return row is not None

# ==================== PAGE STYLE ====================
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

st.markdown("""
<style>
    .stApp { background:#000; color:#fff; }
    h1, h2, h3 { color:#00C853 !important; }
    .stButton>button { background:#00C853; color:#000; font-weight:bold; border:none; border-radius:8px; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background:#111; color:white; }
</style>
""", unsafe_allow_html=True)

# ==================== HEADER WITH YOUR IMAGES ====================
col1, col2 = st.columns([1,5])
with col1:
    if os.path.exists("Untitled_Artwork.png"):
        st.image("Untitled_Artwork.png", width=130)
with col2:
    st.markdown("<h1 style='margin:0;color:#00C853'>CASHIN INK</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0;color:#aaa'>Julio Munoz • Miami</p>", unsafe_allow_html=True)

# Background / hero image
if os.path.exists("IMG_6745.png"):
    st.image("IMG_6745.png", use_column_width=True)

st.markdown("---")

# ==================== BOOKING FORM ====================
st.header("Book Your Tattoo — $150 Deposit Required")
st.info("All appointments are 2 hours • Non-refundable deposit locks your spot")

with st.form("booking_form"):
    st.write("**Your Info**")
    c1, c2 = st.columns(2)
    name  = c1.text_input("Full Name*")
    age   = c2.number_input("Age*", min_value=18, max_value=100, value=18)
    phone = c1.text_input("Phone*")
    email = c2.text_input("Email*")

    description = st.text_area("Tattoo idea (size, placement, style, reference)*", height=110)

    st.write("**Upload Reference Photos / Drawings**")
    uploaded = st.file_uploader("Photos, sketches, PDFs...", accept_multiple_files=True,
                                type=["png","jpg","jpeg","heic","pdf"], label_visibility="collapsed")

    st.markdown("---")
    st.write("**Pick Date & Time (2-hour session)**")
    appt_date = st.date_input("Date", min_value=datetime.today() + timedelta(days=1))
    appt_time = st.time_input("Start Time", value=datetime.strptime("13:00", "%H:%M").time())

    agree = st.checkbox("I am 18+ and agree to the $150 non-refundable deposit*")
    submit = st.form_submit_button("Pay Deposit → Lock My Slot")

    if submit:
        if not all([name, phone, email, description]):
            st.error("Please fill all required fields")
        elif age < 18:
            st.error("Must be 18+")
        elif not agree:
            st.error("You must accept the deposit policy")
        else:
            # Fixed 2-hour slot
            naive_start = datetime.combine(appt_date, appt_time)
            local_start = STUDIO_TZ.localize(naive_start)
            local_end = local_start + timedelta(hours=2)
            utc_start = local_start.astimezone(pytz.UTC)
            utc_end = local_end.astimezone(pytz.UTC)

            if slot_taken(utc_start, utc_end):
                st.error("That time was just booked! Please pick another.")
                st.stop()

            booking_id = str(uuid.uuid4())
            saved_paths = []

            if uploaded:
                folder = os.path.join(UPLOAD_DIR, booking_id)
                os.makedirs(folder, exist_ok=True)
                for file in uploaded:
                    path = os.path.join(folder, file.name)
                    with open(path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_paths.append(path)

            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {"name": f"Deposit – {name} – {appt_date}"},
                            "unit_amount": 15000,
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url=SUCCESS_URL + f"?booking_id={booking_id}",
                    cancel_url=CANCEL_URL,
                    metadata={"booking_id": booking_id},
                )

                c.execute('''
                    INSERT INTO bookings 
                    (id,name,age,phone,email,description,date,time,start_dt,end_dt,
                     deposit_paid,stripe_session_id,files,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    booking_id, name, age, phone, email, description,
                    str(appt_date), str(appt_time),
                    utc_start.isoformat(), utc_end.isoformat(),
                    0, session.id, ",".join(saved_paths), datetime.utcnow().isoformat()
                ))
                conn.commit()

                st.success("Taking you to payment...")
                st.markdown(f"<meta http-equiv='refresh' content='2;url={session.url}'>", unsafe_allow_html=True)
                st.markdown(f"[Click here if not redirected →]({session.url})")

            except Exception as e:
                st.error(f"Error: {e}")

# ==================== MY BOOKINGS ====================
st.markdown("---")
st.header("Current Bookings")

rows = c.execute("SELECT id, name, date, time, deposit_paid, start_dt, end_dt, email FROM bookings ORDER BY date, time").fetchall()

if rows:
    for row in rows:
        bid, name, date, time, paid, sdt, edt, email = row
        status = "PAID – CONFIRMED" if paid else "Awaiting deposit"
        color = "#00C853" if paid else "#FF5722"
        st.markdown(f"**{name}** — {date} @ {time} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

        if paid and sdt and edt:
            start = datetime.fromisoformat(sdt).astimezone(STUDIO_TZ)
            end = datetime.fromisoformat(edt).astimezone(STUDIO_TZ)
            ics = create_ics(f"{bid}@cashinink", f"Cashin Ink Tattoo – {name}", "", start, end, ORGANIZER_EMAIL, email)
            b64 = base64.b64encode(ics).decode()
            st.markdown(f"Download Calendar File → Add to Phone](data:text/calendar;base64,{b64})", unsafe_allow_html=True)
else:
    st.info("No bookings yet.")

# ==================== SUCCESS RETURN ====================
params = st.experimental_get_query_params()
if "booking_id" in params:
    bid = params["booking_id"][0]
    row = c.execute("SELECT name, email, start_dt, end_dt, stripe_session_id FROM bookings WHERE id=?", (bid,)).fetchone()
    if row and stripe.api_key:
        name, email, sdt, edt, session_id = row
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
            conn.commit()
            st.balloons()
            st.success(f"DEPOSIT CONFIRMED! Your spot on {sdt[:10]} is 100% locked, {name}!")
            start = datetime.fromisoformat(sdt).astimezone(STUDIO_TZ)
            end = datetime.fromisoformat(edt).astimezone(STUDIO_TZ)
            ics = create_ics(f"{bid}@cashinink", f"Cashin Ink – {name}", "", start, end, ORGANIZER_EMAIL, email)
            b64 = base64.b64encode(ics).decode()
            st.markdown(f"### Add to Your Calendar](data:text/calendar;base64,{b64})", unsafe_allow_html=True)

st.markdown("---")
st.caption("© 2025 Cashin Ink • Julio Munoz • Miami • All deposits are non-refundable")