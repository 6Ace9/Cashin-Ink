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
    html, body, [class*="css"]  { height: 100%; margin: 0; padding: 0; }
    .stApp {
        background: url("https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/background.png")
                    no-repeat center center fixed;
        background-size: cover !important;
        min-height: 100vh;
        margin: 0; padding: 0;
        display: flex;
        flex-direction: column;
    }
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.86); z-index: -1;
    }

    /* GLASS CARD WITH GREEN GLOW */
    .main {
        background: rgba(22, 22, 28, 0.6);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 26px;
        border: 1px solid rgba(0, 200, 83, 0.4);
        box-shadow: 
            0 10px 40px rgba(0,0,0,0.7),
            0 0 30px rgba(0, 200, 83, 0.4),
            0 0 60px rgba(0, 255, 100, 0.25),
            inset 0 0 20px rgba(0, 255, 100, 0.1);
        margin:  60px auto 20px auto;
        max-width: 960px;
        padding: 25px;
        flex: 1;
    }

    @keyframes pulseGlow {
        from { box-shadow: 0 10px 40px rgba(0,0,0,0.7), 0 0 30px rgba(0,200,83,0.4), 0 0 60px rgba(0,255,100,0.25), inset 0 0 20px rgba(0,255,100,0.1); }
        to   { box-shadow: 0 10px 40px rgba(0,0,0,0.8), 0 0 40px rgba(0,200,83,0.6), 0 0 80px rgba(0,255,100,0.4), inset 0 0 30px rgba(0,255,100,0.15); }
    }

    @keyframes glow {
        from { filter: drop-shadow(0 0 20px #00C853); }
        to   { filter: drop-shadow(0 0 45px #00C853); }
    }
    .logo-glow { animation: glow 4s ease-in-out infinite alternate; border-radius: 20px; }

    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stNumberInput>div>div>input {
        background: rgba(40,40,45,0.9)!important;
        border: 1px solid #00C85340!important;
        border-radius: 14px!important;
        color: white!important;
        padding: 16px!important;
        font-size: 18px!important;
    }

    .stButton>button {
        background: linear-gradient(45deg,#00C853,#00ff6c)!important;
        color: black!important;
        font-weight: bold!important;
        border: none!important;
        border-radius: 18px!important;
        padding: 20px 60px!important;
        font-size: 22px!important;
        min-height: 76px!important;
        box-shadow: 0 10px 30px rgba(0,200,83,0.6)!important;
    }

    h1,h2,h3,h4 { color:#00ff88!important; text-align:center; font-weight:500; }

    /* KILL EVERYTHING AT BOTTOM — 100% GONE */
    footer, [data-testid="stFooter"], .css-1d391kg, .css-1v0mbdj { display:none!important; }
    .block-container { padding-bottom:0!important; margin-bottom:0!important; }
    section.main { margin-bottom:0!important; padding-bottom:0!important; }
    .stApp > div:last-child { padding-bottom:0!important; margin-bottom:0!important; }
</style>
""", unsafe_allow_html=True)

st.markdown('''
<div class="main">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Great+Vibes&display=swap');
</style>

<div style="text-align:center;padding:5px 0 30px 0;">
    <img src="https://raw.githubusercontent.com/6Ace9/Cashin-Ink/refs/heads/main/logo.PNG"
         class="logo-glow" style="width:360px;height:auto;" loading="lazy">
    
    <h3 style="margin-top:20px; color:white; font-family: 'Great Vibes', cursive; 
               font-size:3.2rem; font-weight:400; letter-spacing:4px; 
               text-shadow: 
               0 0 20px #00C853, 
               0 0 40px #00C853, 
               0 0 60px #00ff6c, 
               0 0 80px #00ff6c;
               animation: glow 4s ease-in-out infinite alternate;">
        Cashin Ink
    </h3>
</div>

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
if "appt_date_str" not in st.session_state: st.session_state.appt_date_str = (datetime.now(STUDIO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
if "appt_time_str" not in st.session_state: st.session_state.appt_time_str = "13:00"

# SUCCESS PAGE
if st.query_params.get("success") == "1":
    st.balloons()
    st.success("Payment Confirmed! Your slot is locked.")
    st.info("Julio will contact you within 24 hours. Thank you!")
    # ... (your calendar code — already perfect)
    st.stop()

# MAIN FORM
st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("Non-refundable • Locks your slot")

with st.form("booking_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(213) 555-0192")
    with col2:
        age = st.number_input("Age*", min_value=18, max_value=100, value=25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style)", height=140)

    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded: st.session_state.uploaded_files = uploaded

    st.markdown("### Select Date & Time")

    dc, tc = st.columns(2)
    with dc:
        components.html(f"""
        <input type="date" id="d" value="{st.session_state.appt_date_str}"
               min="{ (datetime.now(STUDIO_TZ)+timedelta(days=1)).strftime('%Y-%m-%d') }"
               max="{ (datetime.now(STUDIO_TZ)+timedelta(days=90)).strftime('%Y-%m-%d') }"
               style="width:95%; height:48px; padding:10px; font-size:16px; background:#1e1e1e; color:white;
                      border:2px solid #00C853; border-radius:12px; text-align:center; box-sizing:border-box;">
        """, height=72)
    with tc:
        components.html(f"""
        <input type="time" id="t" value="{st.session_state.appt_time_str}" step="3600"
               style="width:95%; height:48px; padding:10px; font-size:16px; background:#1e1e1e; color:white;
                      border:2px solid #00C853; border-radius:12px; text-align:center; box-sizing:border-box;">
        """, height=72)

    components.html("""
    <script>
        document.getElementById('d')?.addEventListener('change', e => parent.streamlit.setComponentValue({date: e.target.value}));
        document.getElementById('t')?.addEventListener('change', e => parent.streamlit.setComponentValue({time: e.target.value}));
    </script>
    """, height=0)

    if st.session_state.get("streamlit_component_value"):
        v = st.session_state.streamlit_component_value
        if v.get("date"): st.session_state.appt_date_str = v["date"]
        if v.get("time"): st.session_state.appt_time_str = v["time"]

    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_date = (datetime.now(STUDIO_TZ) + timedelta(days=1)).date()
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if appt_date.weekday() == 6: st.error("Closed on Sundays")
    if appt_time.hour < 12 or appt_time.hour > 20: st.error("Open 12 PM – 8 PM only")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    _, center, _ = st.columns([1, 2.4, 1])
    with center:
        submit = st.form_submit_button("BOOK APPOINTMENT", use_container_width=True)

    if submit:
        if appt_date.weekday() == 6 or appt_time.hour < 12 or appt_time.hour > 20:
            st.error("Invalid date/time"); st.stop()
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Please fill all fields"); st.stop()

        start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
        end_dt = start_dt + timedelta(hours=2)

        conflict = c.execute("SELECT name FROM bookings WHERE start_dt < ? AND end_dt > ?",
                          (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
        if conflict:
            st.error(f"Slot taken by {conflict[0]}"); st.stop()

        bid = str(uuid.uuid4())
        os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
        paths = []
        for f in st.session_state.uploaded_files:
            path = f"{UPLOAD_DIR}/{bid}/{f.name}"
            with open(path, "wb") as out: out.write(f.getbuffer())
            paths.append(path)

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
            bid, name, age, phone, email, description,
            str(appt_date), appt_time.strftime("%-I:%M %p"),
            start_dt.astimezone(pytz.UTC).isoformat(),
            end_dt.astimezone(pytz.UTC).isoformat(),
            0, session.id, ",".join(paths), datetime.utcnow().isoformat()
        ))
        conn.commit()

        st.success("Redirecting to payment…")
        st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
        st.balloons()

# CLOSE CARD
st.markdown("</div>", unsafe_allow_html=True)

# WHITE FOOTER — NO SPACE BELOW
st.markdown("""
<div style="text-align:center; color:white; font-size:16px; font-weight:500; letter-spacing:1px; padding:30px 0 0 0; margin:0;">
    © 2025 Cashin Ink — Covina, CA
</div>
""", unsafe_allow_html=True)

# FINAL KILL SWITCH — 100% NO BOTTOM SPACE
st.markdown("""
<style>
    .stApp { padding-bottom: 0px !important; margin-bottom: 0px !important; }
    body { margin: 0; padding: 0; }
</style>
""", unsafe_allow_html=True)