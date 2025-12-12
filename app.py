# app.py ← FINAL FIXED: Fast loading + Perfect background fit + Glowing logo
import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import base64
import requests

st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

# ==================== FAST IMAGE LOADER ====================
@st.cache_data(ttl=3600)  # Cache images for 1 hour = lightning fast
def img_b64(url):
    try:
        response = requests.get(url, timeout=10)
        return base64.b64encode(response.content).decode()
    except:
        return None

# RAW URLs — these load instantly
logo_b64 = img_b64("https://raw.githubusercontent.com/6Ace9/Cashin-Ink/main/logo.png")
bg_b64   = img_b64("https://raw.githubusercontent.com/6Ace9/Cashin-Ink/main/background.png")

# FORCE PERFECT BACKGROUND FIT + FAST LOAD
bg_css = f"""
    background: linear-gradient(rgba(0,0,0,0.92), rgba(0,0,0,0.88)),
                url('data:image/png;base64,{bg_b64}') center/cover no-repeat fixed;
    background-attachment: fixed;
    image-rendering: -webkit-optimize-contrast;
""" if bg_b64 else "background:#000;"

# LOGO WITH STRONGER NEON GREEN GLOW
logo_html = f"""
<img src="data:image/png;base64,{logo_b64}" class="glowing-logo"
     style="display:block;margin:30px auto;width:380px;
            filter: drop-shadow(0 0 30px #00ff00) drop-shadow(0 0 60px #00C853);
            animation: pulse 4s infinite;">
""" if logo_b64 else "<h1 style='color:#00C853;text-align:center; text-shadow: 0 0 30px #00ff00;'>CASHIN INK</h1>"

st.markdown(f"""
<style>
    .stApp {{
        {bg_css}
        min-height: 100vh;
        margin: 0;
        padding: 0;
    }}
    .main {{
        background: rgba(0,0,0,0.6);
        padding: 30px;
        border-radius: 18px;
        max-width: 900px;
        margin: 20px auto;
        border: 1px solid #00C85350;
        backdrop-filter: blur(8px);
    }}
    h1,h2,h3,h4 {{ color:#00C853 !important; text-align:center; text-shadow: 0 0 20px #00ff00; }}
    .stButton>button {{
        background: linear-gradient(45deg, #00C853, #64dd17) !important;
        color: black !important;
        font-weight: bold;
        border-radius: 12px;
        padding: 18px 50px;
        font-size: 22px;
        border: none;
        box-shadow: 0 0 20px #00ff0030;
    }}
    .centered-button {{ display: flex; justify-content: center; margin-top: 30px; }}
    footer {{ visibility: hidden !important; }}

    /* STRONG NEON GLOW LOGO */
    .glowing-logo {{
        background: transparent !important;
        mix-blend-mode: screen;
        animation: pulse 4s infinite alternate;
    }}
    @keyframes pulse {{
        from {{ filter: drop-shadow(0 0 30px #00ff00); }}
        to   {{ filter: drop-shadow(0 0 50px #00ff00) drop-shadow(0 0 80px #00C853); }}
    }}
</style>

<div style="text-align:center; padding:20px 0;">
    {logo_html}
    <h3 style="margin-top:-10px; color:#00ff88; text-shadow:0 0 20px #00ff00;">
        LA — Premium Tattoo Studio
    </h3>
</div>
<div class="main">
""", unsafe_allow_html=True)

# ==================== DB & STRIPE ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

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
st.header("Book Your Session — $150 Deposit")
st.info("Lock your slot • Non-refundable • Confirmed instantly")

with st.form("booking_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(213) 555-0198")
    with col2:
        age = st.number_input("Age*", 18, 100, 25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style, refs)", height=120)
    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded: st.session_state.uploaded_files = uploaded

    st.markdown("### Select Date & Time")
    dc, tc = st.columns([2,1])

    with dc:
        st.markdown("**Date**")
        components.html(f"""
        <input type="date" id="datePicker" value="{st.session_state.appt_date_str}"
               min="{ (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d') }"
               max="{ (datetime.today() + timedelta(days=90)).strftime('%Y-%m-%d') }"
               style="background:#111;color:#fff;border:2px solid #00C853;border-radius:10px;
                      height:60px;width:240px;font-size:22px;text-align:center;">
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
                   style="background:#111;color:#fff;border:2px solid #00C853;border-radius:10px;
                          height:60px;width:200px;font-size:24px;text-align:center;">
        </div>
        <script>
            const t = document.getElementById('timePicker');
            t.removeAttribute('readonly');
            t.showPicker && t.addEventListener('click', () => t.showPicker());
        </script>
        """, height=180)

    # Sync values
    components.html("""
    <script>
        document.getElementById('datePicker').addEventListener('change', () => 
            parent.streamlit.setComponentValue({date: this.value}));
        document.getElementById('timePicker').addEventListener('change', () => 
            parent.streamlit.setComponentValue({time: this.value}));
    </script>
    """, height=0)

    val = st.session_state.get("streamlit_component_value", {})
    if isinstance(val, dict):
        if val.get("date"): st.session_state.appt_date_str = val["date"]
        if val.get("time"): st.session_state.appt_time_str = val["time"]

    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_date = (datetime.today() + timedelta(days=1)).date()
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if appt_date.weekday() == 6:
        st.error("Closed on Sundays")
        st.stop()
    if appt_time.hour < 12 or appt_time.hour > 20:
        st.error("Open 12:00 PM – 8:00 PM only")
        st.stop()

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    st.markdown("<div class='centered-button'>", unsafe_allow_html=True)
    submit = st.form_submit_button("PAY $150 DEPOSIT → BOOK NOW")
    st.markdown("</div>", unsafe_allow_html=True)

    if submit:
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Please fill all fields and agree to deposit")
        else:
            start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            end_dt = start_dt + timedelta(hours=2)

            conflict = c.execute("SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                               (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
            if conflict:
                st.error(f"Slot taken by {conflict[0]}")
                st.stop()

            bid = str(uuid.uuid4())
            os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
            paths = [f"{UPLOAD_DIR}/{bid}/{f.name}" for f in st.session_state.uploaded_files]
            for f, p in zip(st.session_state.uploaded_files, paths):
                with open(p, "wb") as out: out.write(f.getbuffer())

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
                bid, name, age, phone, email, description, str(appt_date),
                appt_time.strftime("%-I:%M %p"), start_dt.astimezone(pytz.UTC).isoformat(),
                end_dt.astimezone(pytz.UTC).isoformat(), 0, session.id, ",".join(paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Taking you to secure checkout…")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

if st.query_params.get("success"):
    st.success("Payment Successful! Your appointment is confirmed. We'll text/call you soon!")
    st.balloons()

with st.expander("Studio — Upcoming Bookings (Admin View)"):
    for row in c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time"):
        status = "PAID" if row[4] else "PENDING"
        color = "#00ff00" if row[4] else "#ff9800"
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:40px 0 20px;color:#00ff88;font-size:15px;text-shadow:0 0 10px #00ff00;">
    © 2025 Cashin Ink — Covina, CA • By Appointment Only
</div>
""", unsafe_allow_html=True)
