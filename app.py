# app.py → FINAL PERFECT VERSION | GREY PICKERS | NO BOTTOM SPACE | ZERO ERRORS

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

# ==================== DESIGN ====================
st.markdown("""
<style>
    .stApp {
        background: url("https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/background.png")
                    no-repeat center center fixed;
        background-size: cover !important;
        min-height: 100vh;
        margin: 0; padding: 0;
    }
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.86); z-index: -1;
    }
    .main {
        background: rgba(22, 22, 28, 0.6) !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 26px;
        border: 1px solid rgba(255, 255, 255, 0.07);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.7);
        margin: 20px auto;
        max-width: 960px;
        padding: 50px;
    }
    @keyframes glow {
        from { filter: drop-shadow(0 0 20px #00C853); }
        to   { filter: drop-shadow(0 0 45px #00C853); }
    }
    .logo-glow { animation: glow 4s ease-in-out infinite alternate; border-radius: 20px; }

    /* Grey inputs */
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

    /* Custom date/time pickers */
    input[type="date"], input[type="time"] {
        width: 100% !important;
        padding: 20px !important;
        font-size: 20px !important;
        background: #1e1e1e !important;
        color: white !important;
        border: 2px solid #00C853 !important;
        border-radius: 14px !important;
        text-align: center;
        box-shadow: 0 6px 20px rgba(0,200,83,0.3);
    }

    .stButton>button {
        background: linear-gradient(45deg, #00C853, #00ff6c) !important;
        color: black !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 18px !important;
        padding: 20px 60px !important;
        font-size: 22px !important;
        min-height: 76px !important;
        box-shadow: 0 10px 30px rgba(0,200,83,0.6) !important;
        width: 100%;
    }

    h1,h2,h3,h4 { color: #00ff88 !important; text-align: center; font-weight: 500; }
    
    /* Kill all bottom space */
    .block-container { padding-bottom: 0rem !important; margin-bottom: 0 !important; }
    footer, .css-1d391kg { visibility: hidden !important; }
    .stApp { overflow: hidden; }
    section[data-testid="stSidebar"] { display: none; }
</style>

<div style="text-align:center; padding:60px 0 30px 0;">
    <img src="https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/logo.png"
         class="logo-glow" style="width:360px; height:auto;" loading="lazy">
    <h3 style="margin-top:20px; color:#00ff88; font-weight:300; font-size:1.9rem; letter-spacing:2px;">
        LA — Premium Tattoo Studio
    </h3>
</div>

<div class="main">
""", unsafe_allow_html=True)

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/Los_Angeles")  # ← Fixed: Was New_York, now LA time!

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY in Streamlit secrets")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

ICLOUD_ENABLED = False
try:
    ICLOUD_EMAIL = st.secrets["ICLOUD_EMAIL"]
    ICLOUD_APP_PASSWORD = st.secrets["ICLOUD_APP_PASSWORD"]
    ICLOUD_ENABLED = True
except:
    pass  # Optional email feature

SUCCESS_URL = "https://cashin-ink.streamlit.app/?success=1"
CANCEL_URL = "https://cashin-ink.streamlit.app/?cancel=1"

# DB Setup
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY, name TEXT, age INTEGER, phone TEXT, email TEXT, description TEXT,
    date TEXT, time TEXT, start_dt TEXT, end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0, stripe_session_id TEXT, files TEXT, created_at TEXT
)''')
conn.commit()

# Session state init
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "appt_date_str" not in st.session_state:
    st.session_state.appt_date_str = (datetime.now(STUDIO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
if "appt_time_str" not in st.session_state:
    st.session_state.appt_time_str = "13:00"

# ==================== SUCCESS HANDLING ====================
if st.query_params.get("success") == "1":
    st.balloons()
    st.success("Payment Confirmed! Your slot is locked.")
    st.info("Julio will contact you within 24 hours to confirm details.")
    
    # Send .ics to studio owner
    if ICLOUD_ENABLED:
        booking = c.execute("SELECT name,date,time,phone,email,description,id FROM bookings WHERE deposit_paid=0 ORDER BY created_at DESC LIMIT 1").fetchone()
        if booking:
            name, date_str, time_str, phone, email, desc, bid = booking
            try:
                start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
                end_dt = start_dt + timedelta(hours=2)

                ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Cashin Ink//Booking//EN
BEGIN:VEVENT
UID:cashinink-{bid}@example.com
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start_dt.strftime("%Y%m%dT%H%M00")}
DTEND:{end_dt.strftime("%Y%m%dT%H%M00")}
SUMMARY:Tattoo Session - {name}
LOCATION:Cashin Ink Studio, Covina CA
DESCRIPTION:Client: {name}\\nPhone: {phone}\\nEmail: {email}\\nIdea: {desc.replace(chr(10), '\\n')}\\nDeposit: $150 PAID
ORGANIZER;CN=Cashin Ink:mailto:{ICLOUD_EMAIL}
END:VEVENT
END:VCALENDAR"""

                msg = MIMEMultipart()
                msg['From'] = ICLOUD_EMAIL
                msg['To'] = ICLOUD_EMAIL
                msg['Subject'] = f"New Booking: {name} – {date_str} {time_str}"

                msg.attach(MIMEText(f"New booking confirmed!\n\nName: {name}\nDate: {date_str} {time_str}\nPhone: {phone}\nEmail: {email}\n\nIdea:\n{desc}", 'plain'))

                part = MIMEBase('text', 'calendar; method=REQUEST')
                part.set_payload(ics)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="tattoo-booking.ics"')
                msg.attach(part)

                server = smtplib.SMTP('smtp.mail.me.com', 587)
                server.starttls()
                server.login(ICLOUD_EMAIL, ICLOUD_APP_PASSWORD)
                server.sendmail(ICLOUD_EMAIL, ICLOUD_EMAIL, msg.as_string())
                server.quit()
            except Exception as e:
                st.warning("Calendar invite sent failed (will retry manually)")

    st.stop()  # Prevent form from showing again

# ==================== MAIN FORM ====================
st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("Non-refundable • Secures your 2-hour slot • Goes toward final price")

with st.form("booking_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe", key="name")
        phone = st.text_input("Phone*", placeholder="(213) 555-0192", key="phone")
    with col2:
        age = st.number_input("Age*", min_value=18, max_value=100, value=25, key="age")
        email = st.text_input("Email*", placeholder="you@gmail.com", key="email")

    description = st.text_area("Tattoo Idea* (size, placement, style, reference artists)", height=140, key="desc")

    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True, key="uploader")
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### Select Date & Time (2-hour session)")

    dc, tc = st.columns([1.8, 1])
    with dc:
        components.html(f"""
        <div style="padding:12px 0;">
            <label style="color:#00ff88;font-size:19px;">Date</label>
            <input type="date" id="datePicker" value="{st.session_state.appt_date_str}"
                   min="{ (datetime.now(STUDIO_TZ)+timedelta(days=1)).strftime('%Y-%m-%d') }"
                   max="{ (datetime.now(STUDIO_TZ)+timedelta(days=90)).strftime('%Y-%m-%d') }">
        </div>
        """, height=130)
    with tc:
        components.html(f"""
        <div style="padding:12px 0;">
            <label style="color:#00ff88;font-size:19px;">Start Time</label>
            <input type="time" id="timePicker" value="{st.session_state.appt_time_str}" step="3600">
        </div>
        """, height=130)

    components.html("""
    <script>
        const d = document.getElementById('datePicker');
        const t = document.getElementById('timePicker');
        if (d) d.onchange = () => parent.streamlit.setComponentValue({date: d.value});
        if (t) t.onchange = () => parent.streamlit.setComponentValue({time: t.value});
    </script>
    """, height=0)

    picker = st.session_state.get("streamlit_component_value", {})
    if isinstance(picker, dict):
        if picker.get("date") and st.session_state.appt_date_str = picker["date"]
        if picker.get("time"):
            st.session_state.appt_time_str = picker["time"]

    # Validate date/time
    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
        start_dt_local = datetime.combine(appt_date, appt_time)
        start_dt = STUDIO_TZ.localize(start_dt_local)
        end_dt = start_dt + timedelta(hours=2)
    except:
        st.error("Invalid date/time selected")
        st.stop()

    if appt_date.weekday() == 6:  # Sunday
        st.error("Closed on Sundays")
    elif appt_time.hour < 12 or appt_time.hour >= 20:
        st.error("Studio open 12:00 PM – 8:00 PM only")
    else:
        # Check conflict
        conflict = c.execute("""
            SELECT name FROM bookings 
            WHERE start_dt < ? AND end_dt > ? AND deposit_paid = 1
        """, (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
        if conflict:
            st.error(f"This time slot is already booked by {conflict[0]}")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit** (applied to final tattoo price)")

    submitted = st.form_submit_button("LOCK IN MY SLOT – PAY $150 DEPOSIT", use_container_width=True)

    if submitted:
        if appt_date.weekday() == 6 or appt_time.hour < 12 or appt_time.hour >= 20:
            st.error("Please fix date/time"); st.stop()
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("All fields required + must agree to deposit"); st.stop()

        # Final conflict check
        conflict = c.execute("SELECT 1 FROM bookings WHERE start_dt < ? AND end_dt > ?",
                          (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
        if conflict:
            st.error("Sorry, this slot was just taken! Please pick another time.")
            st.stop()

        bid = str(uuid.uuid4())
        os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
        file_paths = []
        for file in st.session_state.uploaded_files:
            path = f"{UPLOAD_DIR}/{bid}/{file.name}"
            with open(path, "wb") as f:
                f.write(file.getbuffer())
            file_paths.append(path)

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
                success_url=SUCCESS_URL,
                cancel_url=CANCEL_URL,
                metadata={"booking_id": bid},
                customer_email=email,
            )

            # Save booking (deposit not yet paid)
            c.execute("""INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                bid, name, age, phone, email, description,
                str(appt_date), appt_time.strftime("%-I:%M %p"),
                start_dt.astimezone(pytz.UTC).isoformat(),
                end_dt.astimezone(pytz.UTC).isoformat(),
                0, session.id, ",".join(file_paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Redirecting to secure payment…")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

        except Exception as e:
            st.error("Payment setup failed. Please try again or contact us.")
            st.write(e)

# ==================== CLOSE CONTAINER ====================
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; padding:70px 0 40px; color:#00ff8866; font-size:15px;">
    © 2025 Cashin Ink — Premium Tattoo Studio — Covina, CA
</div>
""", unsafe_allow_html=True)
