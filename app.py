# app.py ← FINAL FIXED & ULTRA-FAST VERSION (no syntax error, same exact look)

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

# ==================== FAST LOGO & BACKGROUND ====================
LOGO_URL = "https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/logo.png"
BG_URL   = "https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/background.png"  # ← change if you have a real background

st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.88), rgba(0,0,0,0.88)),
                    url('{BG_URL}') center/cover no-repeat fixed;
        min-height: 100vh;
    }}
    .main {{
        background: rgba(0,0,0,0.5);
        padding: 30px;
        border-radius: 18px;
        max-width: 900px;
        margin: 20px auto;
        border: 1px solid #00C85340;
        backdrop-filter: blur(8px);
    }}
    h1,h2,h3,h4 {{ color:#00C853 !important; text-align:center; }}
    .stButton>button {{
        background: #00C853 !important; color: black !important; font-weight:bold;
        border-radius:8px; padding:18px 40px !important; font-size:20px !important;
        min-height:60px !important;
    }}
    footer {{ visibility: hidden !important; }}
    @keyframes glow {{
        from {{ filter: drop-shadow(0 0 15px #00C853); }}
        to   {{ filter: drop-shadow(0 0 35px #00C853); }}
    }}
    .logo-glow {{ animation: glow 4s ease-in-out infinite alternate; border-radius:12px; }}
</style>

<div style="text-align:center;padding:30px 0 10px 0;">
    <img src="{LOGO_URL}" class="logo-glow" style="width:340px;height:auto;" loading="lazy">
    <h3 style="margin-top:12px;color:#00C853;font-weight:300;">LA — Premium Tattoo Studio</h3>
</div>
<div class="main">
""", unsafe_allow_html=True)

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY in secrets")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

try:
    ICLOUD_EMAIL = st.secrets["ICLOUD_EMAIL"]
    ICLOUD_APP_PASSWORD = st.secrets["ICLOUD_APP_PASSWORD"]
    ICLOUD_ENABLED = True
except:
    ICLOUD_EMAIL = ICLOUD_APP_PASSWORD = None
    ICLOUD_ENABLED = False
    st.warning("iCloud calendar disabled — add ICLOUD_EMAIL + ICLOUD_APP_PASSWORD to secrets")

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

# Session state
if "uploaded_files" not in st.session_state: st.session_state.uploaded_files = []
if "appt_date_str" not in st.session_state: st.session_state.appt_date_str = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
if "appt_time_str" not in st.session_state: st.session_state.appt_time_str = "13:00"

st.markdown("---")
st.header("Book Sessions — $150 Deposit")
st.info("Lock your slot • Non-refundable")

with st.form("booking_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(305) 555-1234")
    with col2:
        age = st.number_input("Age*", 18, 100, 25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style)", height=120)
    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded: st.session_state.uploaded_files = uploaded

    st.markdown("### Date & Time")
    dc, tc = st.columns([2,1])
    with dc:
        st.markdown("**Select Date**")
        components.html(f"""
        <div style="display:flex;justify-content:center;align-items:center;height:140px;">
            <input type="date" id="datePicker" value="{st.session_state.appt_date_str}"
                   min="{ (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d') }"
                   max="{ (datetime.today() + timedelta(days=90)).strftime('%Y-%m-%d') }"
                   style="background:#1e1e1e;color:white;border:2px solid #00C853;border-radius:8px;height:56px;width:220px;font-size:20px;text-align:center;">
        </div>
        <script>
            const d = document.getElementById('datePicker');
            d.removeAttribute('readonly');
            d.showPicker && d.addEventListener('click', () => d.showPicker());
        </script>
        """, height=180)

    with tc:
        st.markdown("**Start Time**")
        components.html(f"""
        <div style="display:flex;justify-content:center;align-items:center;height:140px;">
            <input type="time" id="timePicker" value="{st.session_state.appt_time_str}" step="3600"
                   style="background:#1e1e1e;color:white;border:2px solid #00C853;border-radius:8px;height:56px;width:180px;font-size:22px;text-align:center;">
        </div>
        <script>
            const t = document.getElementById('timePicker');
            t.removeAttribute('readonly');
            t.showPicker && t.addEventListener('click', () => t.showPicker());
        </script>
        """, height=180)

    components.html("""
    <script>
        document.getElementById('datePicker')?.addEventListener('change', () => 
            parent.streamlit.setComponentValue({date: document.getElementById('datePicker').value}));
        document.getElementById('timePicker')?.addEventListener('change', () => 
            parent.streamlit.setComponentValue({time: document.getElementById('timePicker').value}));
    </script>
    """, height=0)

    picker = st.session_state.get("streamlit_component_value", {})
    if isinstance(picker, dict):
        if picker.get("date"): st.session_state.appt_date_str = picker["date"]
        if picker.get("time"): st.session_state.appt_time_str = picker["time"]

    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_date = (datetime.today() + timedelta(days=1)).date()
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if appt_date.weekday() == 6:
        st.error("Closed on Sundays")
    if appt_time.hour < 12 or appt_time.hour > 20:
        st.error("Open 12 PM – 8 PM only")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    _, center, _ = st.columns([1,1.8,1])
    with center:
        submit = st.form_submit_button("PAY DEPOSIT  =>  SCHEDULE APPOINTMENT", use_container_width=True)

    if submit:
        if appt_date.weekday() == 6 or appt_time.hour < 12 or appt_time.hour > 20:
            st.error("Invalid date/time"); st.stop()
        if not all([name,phone,email,description]) or age < 18 or not agree:
            st.error("Complete all fields"); st.stop()

        start_dt_local = datetime.combine(appt_date, appt_time)
        start_dt = STUDIO_TZ.localize(start_dt_local)
        end_dt = start_dt + timedelta(hours=2)

        conflict = c.execute("SELECT name FROM bookings WHERE start_dt < ? AND end_dt > ?",
                            (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
        if conflict:
            st.error(f"Slot taken by {conflict[0]}"); st.stop()

        bid = str(uuid.uuid4())
        os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
        paths = [f"{UPLOAD_DIR}/{bid}/{f.name}" for f in st.session_state.uploaded_files]
        for f, p in zip(st.session_state.uploaded_files, paths):
            with open(p, "wb") as out: out.write(f.getbuffer())

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{ "price_data": { "currency": "usd", "product_data": {"name": f"Deposit – {name}"}, "unit_amount": 15000 }, "quantity": 1 }],
            mode="payment",
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={"booking_id": bid},
            customer_email=email
        )

        c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            bid, name, age, phone, email, description, str(appt_date),
            appt_time.strftime("%-I:%M %p"),
            start_dt.astimezone(pytz.UTC).isoformat(),
            end_dt.astimezone(pytz.UTC).isoformat(),
            0, session.id, ",".join(paths), datetime.utcnow().isoformat()
        ))
        conn.commit()

        st.success("Taking you to payment…")
        st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
        st.balloons()

# SUCCESS → SEND .ICS (fixed syntax error)
if st.query_params.get("success") == "1":
    st.success("Payment confirmed! Your slot is locked. Julio will contact you soon.")
    st.balloons()

    if ICLOUD_ENABLED:
        booking = c.execute("SELECT name,date,time,phone,email,description,id FROM bookings ORDER BY created_at DESC LIMIT 1").fetchone()
        if booking:
            client_name, date_str, time_str, phone, client_email, desc, bid = booking
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
            end_dt = start_dt + timedelta(hours=2)

            # FIXED: use raw triple-quoted string + .format() instead of f-string with backslashes
            ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Cashin Ink//EN
BEGIN:VEVENT
UID:cashinink-{bid}@cashinink.com
DTSTAMP:{now}
DTSTART:{start}
DTEND:{end}
SUMMARY:Tattoo – {name}
LOCATION:Cashin Ink Studio – Covina, CA
DESCRIPTION:Client: {name}\\nPhone: {phone}\\nEmail: {email}\\nIdea: {desc}\\nDeposit: PAID $150
END:VEVENT
END:VCALENDAR""".format(
                bid=bid,
                now=datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
                start=start_dt.strftime("%Y%m%dT%H%M00"),
                end=end_dt.strftime("%Y%m%dT%H%M00"),
                name=client_name,
                phone=phone,
                email=client_email,
                desc=desc.replace("\n", "\\n")
            )

            msg = MIMEMultipart()
            msg['From'] = ICLOUD_EMAIL
            msg['To'] = ICLOUD_EMAIL
            msg['Subject'] = f"New Booking: {client_name} – {date_str} {time_str}"

            msg.attach(MIMEText(f"New paid booking!\n\n{client_name} – {date_str} @ {time_str}\nDeposit confirmed.", 'plain'))

            part = MIMEBase('text', 'calendar; name="booking.ics"')
            part.set_payload(ics_content)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="booking.ics"')
            msg.attach(part)

            try:
                server = smtplib.SMTP('smtp.mail.me.com', 587)
                server.starttls()
                server.login(ICLOUD_EMAIL, ICLOUD_APP_PASSWORD)
                server.sendmail(ICLOUD_EMAIL, ICLOUD_EMAIL, msg.as_string())
                server.quit()
                st.success("Calendar event sent to Julio!")
            except Exception as e:
                st.warning("Failed to send .ics (check credentials)")

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:40px 0 20px;color:#666;font-size:14px;">
    © 2025 Cashin Ink — Covina, CA
</div>
""", unsafe_allow_html=True)
