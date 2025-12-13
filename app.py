# app.py → FINAL | EXACT SAME COLORS | ONLY SIZE + PLACEMENT FIXED | MOBILE PERFECT

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

st.markdown("""
<style>
    .stApp {
        background: url("https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/background.png") 
                    no-repeat center center fixed !important;
        background-size: cover !important;
        min-height: 100vh; margin: 0; padding: 0;
    }
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.86); z-index: -1;
    }
    .main-card {
        background: rgba(22, 22, 28, 0.6);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 26px;
        border: 1px solid rgba(255, 255, 255, 0.07);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.7);
        margin: 15px auto;
        max-width: 960px;
        padding: 45px 35px;
    }
    @keyframes glow {
        from { filter: drop-shadow(0 0 20px #00C853); }
        to   { filter: drop-shadow(0 0 45px #00C853); }
    }
    .logo-glow { animation: glow 4s ease-in-out infinite alternate; border-radius: 20px; }

    /* YOUR ORIGINAL INPUTS — UNTOUCHED */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input {
        background: rgba(40, 40, 45, 0.9) !important;
        border: 1px solid #00C85340 !important;
        border-radius: 14px !important;
        color: white !important;
        padding: 16px !important;
        font-size: 18px !important;
    }

    /* DATE & TIME PICKERS — SAME COLOR, JUST SMALLER & BETTER PLACED */
    input[type="date"], input[type="time"] {
        width: 100% !important;
        padding: 14px !important;
        font-size: 16px !important;
        background: #1e1e1e !important;
        color: white !important;
        border: 2px solid #00C853 !important;
        border-radius: 12px !important;
        text-align: center;
        box-shadow: 0 5px 18px rgba(0,200,83,0.4);
        margin: 6px 0;
    }

    .stButton>button {
        background: linear-gradient(45deg, #00C853, #00ff6c) !important;
        color: black !important;
        font-weight: bold !important;
        border-radius: 18px !important;
        padding: 20px !important;
        font-size: 22px !important;
        min-height: 72px !important;
        box-shadow: 0 10px 30px rgba(0,200,83,0.6) !important;
        width: 100%;
    }

    h1,h2,h3,h4 { color: #00ff88 !important; text-align: center; }

    footer, [data-testid="stFooter"] { display: none !important; }
    .block-container { padding-bottom: 0 !important; margin-bottom: 0 !important; }

    @media (max-width: 768px) {
        .main-card { padding: 35px 22px; margin: 10px; }
        input[type="date"], input[type="time"] { padding: 13px; font-size: 15.5px; }
    }
</style>

<div style="text-align:center; padding:60px 0 30px 0;">
    <img src="https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/logo.png"
         class="logo-glow" style="width:360px; height:auto;" loading="lazy">
    <h3 style="margin-top:20px; color:#00ff88; font-weight:300; font-size:1.9rem; letter-spacing:2px;">
        LA — Premium Tattoo Studio
    </h3>
</div>

<div class="main-card">
""", unsafe_allow_html=True)

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/Los_Angeles")

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

ICLOUD_ENABLED = "ICLOUD_EMAIL" in st.secrets and "ICLOUD_APP_PASSWORD" in st.secrets
if ICLOUD_ENABLED:
    ICLOUD_EMAIL = st.secrets["ICLOUD_EMAIL"]
    ICLOUD_APP_PASSWORD = st.secrets["ICLOUD_APP_PASSWORD"]

SUCCESS_URL = "https://cashin-ink.streamlit.app/?success=1"
CANCEL_URL = "https://cashin-ink.streamlit.app"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY, name TEXT, age INTEGER, phone TEXT, email TEXT, description TEXT,
    date TEXT, time TEXT, start_dt TEXT, end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0, stripe_session_id TEXT, files TEXT, created_at TEXT
)''')
conn.commit()

if "uploaded_files" not in st.session_state: st.session_state.uploaded_files = []
if "appt_date_str" not in st.session_state:
    st.session_state.appt_date_str = (datetime.now(STUDIO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
if "appt_time_str" not in st.session_state:
    st.session_state.appt_time_str = "13:00"

# ==================== SUCCESS PAGE ====================
if st.query_params.get("success") == "1":
    st.balloons()
    st.success("Payment Confirmed! Your slot is locked.")
    st.info("Julio will contact you within 24 hours. Thank you!")

    if ICLOUD_ENABLED:
        booking = c.execute("SELECT name,date,time,phone,email,description,id FROM bookings WHERE deposit_paid=0 ORDER BY created_at DESC LIMIT 1").fetchone()
        if booking:
            name, date_str, time_str, phone, email, desc, bid = booking
            try:
                start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
                end_dt = start_dt + timedelta(hours=2)

                ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:cashinink-{bid}
DTSTAMP:{now}
DTSTART:{start}
DTEND:{end}
SUMMARY:Tattoo - {name}
LOCATION:Cashin Ink Studio, Covina CA
DESCRIPTION:Client: {name}\\nPhone: {phone}\\nEmail: {email}\\nIdea: {desc}\\nDeposit: PAID
END:VEVENT
END:VCALENDAR""".format(
                    bid=bid, now=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
                    start=start_dt.strftime("%Y%m%dT%H%M00"), end=end_dt.strftime("%Y%m%dT%H%M00"),
                    name=name, phone=phone, email=email, desc=desc.replace("\n","\\n")
                )

                msg = MIMEMultipart()
                msg['From'] = msg['To'] = ICLOUD_EMAIL
                msg['Subject'] = f"New Booking: {name}"
                msg.attach(MIMEText(f"New booking: {name} on {date_str} {time_str}", 'plain'))
                part = MIMEBase('text', 'calendar')
                part.set_payload(ics_content)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="booking.ics"')
                msg.attach(part)
                s = smtplib.SMTP('smtp.mail.me.com', 587)
                s.starttls()
                s.login(ICLOUD_EMAIL, ICLOUD_APP_PASSWORD)
                s.sendmail(ICLOUD_EMAIL, ICLOUD_EMAIL, msg.as_string())
                s.quit()
            except: pass
            c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
            conn.commit()
    st.stop()

# ==================== MAIN FORM ====================
st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("Non-refundable • Locks your slot")

with st.form("booking_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(213) 555-0192")
    with col2:
        age = st.number_input("Age*", 18, 100, 25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style)", height=140)

    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### Select Date & Time")
    
    # SMALLER, PERFECTLY PLACED PICKERS — SAME GREEN, SAME VIBE
    dc, tc = st.columns([1.7, 1])
    with dc:
        components.html(f"""
        <input type="date" id="d" value="{st.session_state.appt_date_str}"
               min="{ (datetime.now(STUDIO_TZ)+timedelta(days=1)).strftime('%Y-%m-%d') }"
               max="{ (datetime.now(STUDIO_TZ)+timedelta(days=90)).strftime('%Y-%m-%d') }">
        """, height=80)
    with tc:
        components.html(f"""
        <input type="time" id="t" value="{st.session_state.appt_time_str}" step="3600">
        """, height=80)

    components.html("""
    <script>
        document.getElementById('d')?.addEventListener('change', (e) => 
            parent.streamlit.setComponentValue({date: e.target.value}));
        document.getElementById('t')?.addEventListener('change', (e) => 
            parent.streamlit.setComponentValue({time: e.target.value}));
    </script>
    """, height=0)

    if st.session_state.get("streamlit_component_value"):
        v = st.session_state.streamlit_component_value
        if v.get("date"): st.session_state.appt_date_str = v["date"]
        if v.get("time"): st.session_state.appt_time_str = v["time"]

    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
        start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
        end_dt = start_dt + timedelta(hours=2)
    except:
        st.error("Please select date & time")
        st.stop()

    if appt_date.weekday() == 6: st.error("Closed Sundays")
    if appt_time.hour < 12 or appt_time.hour >= 20: st.error("Open 12 PM – 8 PM only")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    submitted = st.form_submit_button("LOCK IN MY SLOT – PAY $150", use_container_width=True)

    if submitted:
        if not all([name, phone, email, description, agree]) or age < 18:
            st.error("Fill all fields"); st.stop()
        if appt_date.weekday() == 6 or not (12 <= appt_time.hour < 20):
            st.error("Invalid time"); st.stop()

        conflict = c.execute("SELECT 1 FROM bookings WHERE ? > start_dt AND ? < end_dt",
                           (start_dt.astimezone(pytz.UTC).isoformat(), end_dt.astimezone(pytz.UTC).isoformat())).fetchone()
        if conflict:
            st.error("Slot just taken"); st.stop()

        bid = str(uuid.uuid4())
        os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
        paths = []
        for f in st.session_state.uploaded_files:
            path = f"{UPLOAD_DIR}/{bid}/{f.name}"
            with open(path, "wb") as out: out.write(f.getbuffer())
            paths.append(path)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "usd", "product_data": {"name": f"Deposit – {name}"}, "unit_amount": 15000}, "quantity": 1}],
            mode="payment",
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={"booking_id": bid},
            customer_email=email
        )

        c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            bid, name, age, phone, email, description,
            str(appt_date), appt_time.strftime("%-I:%M %p"),
            start_dt.astimezone(pytz.UTC).isoformat(),
            end_dt.astimezone(pytz.UTC).isoformat(),
            0, session.id, ",".join(paths), datetime.utcnow().isoformat()
        ))
        conn.commit()

        st.success("Redirecting…")
        st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
        st.balloons()

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center; padding:70px 0 30px; color:#444; font-size:15px;'>© 2025 Cashin Ink — Covina, CA</div>", unsafe_allow_html=True)
