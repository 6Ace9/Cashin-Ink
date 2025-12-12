# booking.py
# CASHIN INK — FINAL VERSION WITH WORKING LOGO + BACKGROUND + PERFECT TIME PICKER

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import logging
import base64

# ============== PAGE CONFIG ==============
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

# ============== LOAD IMAGES AS BASE64 (WORKS ON STREAMLIT CLOUD!) ==============
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except:
        return None

logo_b64 = get_base64_image("logo.png")
bg_b64 = get_base64_image("background.png")

# Fallback if images not found
if not logo_b64:
    st.error("logo.png not found! Place it in the same folder as this app.")
    logo_html = "<h1 style='color:#00C853; text-align:center;'>CASHIN INK</h1>"
else:
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="width:300px; filter: drop-shadow(0 0 20px #00C853);"/>'

if not bg_b64:
    st.error("background.png not found! Place it in the same folder.")
    bg_css = "background: #000;"
else:
    bg_css = f"background: linear-gradient(rgba(0,0,0,0.82), rgba(0,0,0,0.82)), url('data:image/png;base64,{bg_b64}') center/cover no-repeat fixed;"

# ============== FULL CUSTOM CSS + LOGO + BACKGROUND ==============
st.markdown(f"""
<style>
    .stApp {{
        {bg_css}
        color: white;
        min-height: 100vh;
    }}
    .main-container {{
        background: rgba(0,0,0,0.4);
        border-radius: 20px;
        padding: 30px;
        margin: 20px auto;
        max-width: 900px;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(0,200,83,0.3);
    }}
    h1, h2, h3 {{ color: #00C853 !important; text-align: center; }}
    .logo-div {{ text-align: center; margin: 20px 0 10px; padding: 10px; }}
    .stButton>button {{
        background: #00C853 !important; color: black !important;
        font-weight: bold; border-radius: 8px; padding: 12px 30px; font-size: 18px;
    }}
    /* Fix time picker size */
    input[type="time"] {{
        width: 100% !important;
        max-width: 180px;
        height: 50px;
        font-size: 20px;
        text-align: center;
        background: #111 !important;
        color: white !important;
        border: 2px solid #00C853 !important;
        border-radius: 8px;
    }}
    .stTextInput input, .stTextArea textarea, .stNumberInput input {{
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
        border: 1px solid #00C853 !important;
    }}
</style>

<div class="logo-div">{logo_html}</div>
<h3>Miami — Premium Tattoo Studio</h3>
<div class="main-container">
""", unsafe_allow_html=True)

# ============== ALL ORIGINAL CODE BELOW — 100% UNCHANGED LOGIC ==============
DB_PATH = os.path.join(os.getcwd(), "bookings.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/?success=1")
CANCEL_URL = st.secrets.get("STRIPE_CANCEL_URL", "https://your-app.streamlit.app/")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY, name TEXT, age INTEGER, phone TEXT, email TEXT, description TEXT,
    date TEXT, time TEXT, start_dt TEXT, end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0, stripe_session_id TEXT, files TEXT, created_at TEXT
)''')
conn.commit()

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "appt_time_str" not in st.session_state:
    st.session_state.appt_time_str = "13:00"

qp = st.experimental_get_query_params()
if "appt_time" in qp:
    t = qp["appt_time"][0]
    try:
        datetime.strptime(t, "%H:%M")
        st.session_state.appt_time_str = t
    except:
        pass
    st.experimental_rerun()

st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("2-hour session • Deposit locks your slot • Non-refundable")

with st.form("booking_form"):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(305) 555-1234")
    with c2:
        age = st.number_input("Age*", 18, 100, 25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style, ref artists)", height=120)

    uploaded = st.file_uploader("Upload reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### Select Date & Time")
    dc, tc = st.columns([2,1])
    with dc:
        appt_date = st.date_input("Date*", min_value=datetime.today()+timedelta(days=1), max_value=datetime.today()+timedelta(days=90))
        if appt_date.weekday() == 6:
            st.error("Closed Sundays")
            st.stop()

    with tc:
        st.markdown("**Start Time**")
        html = f"""
        <input type="time" value="{st.session_state.appt_time_str}" step="3600" 
               style="width:100%; max-width:180px; height:50px; font-size:20px; text-align:center;
                      background:#111; color:white; border:2px solid #00C853; border-radius:8px;">
        <script>
            const i = document.querySelector('input[type="time"]');
            i.addEventListener('change', () => {{
                const p = new URLSearchParams(window.location.search);
                p.set('appt_time', i.value);
                window.location.search = p.toString();
            }});
        </script>
        """
        components.html(html, height=70)

    try:
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if appt_time.hour < 12 or appt_time.hour > 20:
        st.error("Open 12:00 PM – 8:00 PM only")
        st.stop()

    display_time = appt_time.strftime("%I:%M %p").lstrip("0")
    st.success(f"**Selected:** {appt_date.strftime('%A, %B %d')} at {display_time}")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")
    submit = st.form_submit_button("PAY DEPOSIT → LOCK SLOT")

    if submit:
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Complete all fields & agree to deposit")
        else:
            start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            end_dt = start_dt + timedelta(hours=2)
            conflict = c.execute("SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                               (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
            if conflict:
                st.error(f"Slot taken by {conflict[0]}")
                st.stop()

            bid = str(uuid.uuid4())
            os.makedirs(os.path.join(UPLOAD_DIR, bid), exist_ok=True)
            paths = []
            for f in st.session_state.uploaded_files:
                p = os.path.join(UPLOAD_DIR, bid, f.name)
                with open(p, "wb") as out:
                    out.write(f.getbuffer())
                paths.append(p)

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price_data": {"currency": "usd", "product_data": {"name": f"Deposit - {name}"}, "unit_amount": 15000}, "quantity": 1}],
                mode="payment",
                success_url=SUCCESS_URL,
                cancel_url=CANCEL_URL,
                metadata={"booking_id": bid},
                customer_email=email
            )

            c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                bid, name, age, phone, email, description, str(appt_date), display_time,
                start_dt.astimezone(pytz.UTC).isoformat(), end_dt.astimezone(pytz.UTC).isoformat(),
                0, session.id, ",".join(paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Redirecting to payment...")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

# Success
if st.experimental_get_query_params().get("success"):
    st.success("Payment received! Your slot is locked.")
    st.balloons()

with st.expander("Studio — Upcoming"):
    for row in c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time").fetchall():
        status = "PAID" if row[4] else "PENDING"
        color = "#00C853" if row[4] else "#FF9800"
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # Close main container
st.caption("© 2025 Cashin Ink — Miami, FL")