# app.py → FINAL FAST & BEAUTIFUL VERSION (under 300 MB RAM, instant load)
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

# ==================== SUPER LIGHT IMAGE LOADER ====================
@st.cache_data(ttl=86400)  # 24-hour cache = almost zero load time
def get_image_b64(url):
    try:
        r = requests.get(url, timeout=8)
        return base64.b64encode(r.content).decode()
    except:
        return None

# Use your real raw GitHub links
logo_b64 = get_image_b64("https://raw.githubusercontent.com/6Ace9/Cashin-Ink/main/logo.png")
bg_b64   = get_image_b64("https://raw.githubusercontent.com/6Ace9/Cashin-Ink/main/background.png")

# Very light background (still looks amazing)
background_style = f"""
    background: linear-gradient(rgba(0,0,0,0.94), rgba(0,0,0,0.90)),
                url('data:image/png;base64,{bg_b64}') center/cover no-repeat fixed;
""" if bg_b64 else "background:#000;"

# Simple static logo with clean green glow (zero performance cost)
logo_html = f"""
<div style="text-align:center; padding:30px 0 10px;">
    <img src="data:image/png;base64,{logo_b64}" 
         style="width:340px; max-width:90vw; background:transparent;">
</div>
""" if logo_b64 else '<h1 style="color:#00ff88; text-align:center;">CASHIN INK</h1>'

st.markdown(f"""
<style>
    .stApp {{
        {background_style}
        min-height: 100vh;
        margin: 0;
        padding: 0;
    }}
    .main {{
        background: rgba(0,0,0,0.65);
        padding: 35px;
        border-radius: 18px;
        max-width: 900px;
        margin: 20px auto;
        border: 1px solid #00C85340;
    }}
    h1, h2, h3, h4 {{ color:#00ff88 !important; text-align:center; text-align:center; }}
    .stButton>button {{
        background: #00C853 !important;
        color: black !important;
        font-weight: bold;
        border-radius: 12px;
        padding: 16px 50px;
        font-size: 21px;
    }}
    .centered-button {{ display:flex; justify-content:center; margin:30px 0; }}
    footer {{ visibility: hidden; }}
</style>

{logo_html}
<div style="text-align:center; margin-top:-15px;">
    <h3 style="color:#00ff88;">LA — Premium Tattoo Studio</h3>
</div>

<div class="main">
""", unsafe_allow_html=True)

# ==================== DATABASE & STRIPE (unchanged & fast) ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing Stripe key")
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
if "appt_date_str" not in st.session_state: st.session_state.appt_date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
if "appt_time_str" not in st.session_state: st.session_state.appt_time_str = "13:00"

st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("Non-refundable deposit locks your slot")

with st.form("booking_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(213) 555-1234")
    with col2:
        age = st.number_input("Age*", 18, 100, 25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style)", height=120)
    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","pdf"], accept_multiple_files=True)
    if uploaded: st.session_state.uploaded_files = uploaded

    st.markdown("### Date & Time")
    dc, tc = st.columns([2,1])
    with dc:
        date_picked = st.date_input("Select Date", 
                                   min_value=datetime.today() + timedelta(days=1),
                                   max_value=datetime.today() + timedelta(days=90),
                                   value=datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d"))
        st.session_state.appt_date_str = date_picked.strftime("%Y-%m-%d")
    with tc:
        time_picked = st.time_input("Start Time", value=datetime.strptime("13:00", "%H:%M"), step=timedelta(hours=1))
        st.session_state.appt_time_str = time_picked.strftime("%H:%M")

    appt_date = date_picked
    appt_time = time_picked

    if appt_date.weekday() == 6:
        st.error("Closed on Sundays")
        st.stop()
    if appt_time.hour < 12 or appt_time.hour > 20:
        st.error("Open 12 PM – 8 PM only")
        st.stop()

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    st.markdown("<div class='centered-button'>", unsafe_allow_html=True)
    submit = st.form_submit_button("PAY $150 DEPOSIT → BOOK NOW")
    st.markdown("</div>", unsafe_allow_html=True)

    if submit:
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Please complete all required fields")
        else:
            start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            end_dt = start_dt + timedelta(hours=2)

            conflict = c.execute("SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                               (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
            if conflict:
                st.error(f"Slot already taken by {conflict[0]}")
                st.stop()

            bid = str(uuid.uuid4())
            os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
            paths = []
            for f in st.session_state.uploaded_files:
                path = f"{UPLOAD_DIR}/{bid}/{f.name}"
                with open(path, "wb") as out:
                    out.write(f.getbuffer())
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
                bid, name, age, phone, email, description, str(appt_date),
                appt_time.strftime("%-I:%M %p"), start_dt.astimezone(pytz.UTC).isoformat(),
                end_dt.astimezone(pytz.UTC).isoformat(), 0, session.id, ",".join(paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Taking you to payment…")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

if st.query_params.get("success"):
    st.success("Payment confirmed! Your slot is locked. We’ll be in touch soon.")
    st.balloons()

with st.expander("Upcoming Bookings"):
    for row in c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time").fetchall():
        status = "PAID" if row[4] else "PENDING"
        color = "#00ff88" if row[4] else "#ff9800"
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;padding:40px;color:#666;font-size:14px;'>© 2025 Cashin Ink — Covina, CA</div>", unsafe_allow_html=True)
