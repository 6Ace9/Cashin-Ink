# booking.py
# ==================== CASHIN INK — BOOKING APP V2 (WITH PROFESSIONAL LOGO + BACKGROUND) ====================

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import logging

# ============== PAGE CONFIG ==============
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="💉")

# ============== CUSTOM CSS WITH LOGO & BACKGROUND ==============
st.markdown(f"""
<style>
    /* Full Background Image */
    .stApp {{
        background: url("background.png") no-repeat center center fixed;
        background-size: cover;
        color: white;
    }}

    /* Dark overlay for readability */
    .stApp::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.78);
        z-index: -1;
    }}

    /* Logo at top */
    .logo-container {{
        text-align: center;
        margin: 20px 0 10px 0;
        padding: 15px;
    }}
    .logo-container img {{
        width: 280px;
        filter: drop-shadow(0 0 15px rgba(0, 200, 83, 0.6));
    }}

    /* Titles & Text */
    h1, h2, h3, h4 {{
        color: #00C853 !important;
        text-align: center;
        font-weight: 800;
    }}
    .stMarkdown, .stCaption, p, label, .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea, .stDateInput > div > div > input {{
        color: white !important;
    }}

    /* Buttons */
    .stButton > button {{
        background: #00C853 !important;
        color: black !important;
        font-weight: bold;
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 18px;
    }}

    /* Form inputs */
    div[data-baseweb="select"] > div, .stSelectbox > div > div {{
        background-color: rgba(255,255,255,0.1) !important;
        color: white !important;
    }}

    /* Success/Error messages */
    .stSuccess, .stInfo, .stWarning {{
        background-color: rgba(0, 200, 83, 0.15);
        border-left: 5px solid #00C853;
    }}
    .stError {{
        background-color: rgba(244, 67, 54, 0.15);
        border-left: 5px solid #f44336;
    }}

    /* Expander */
    .streamlit-expanderHeader {{
        background-color: rgba(255,255,255,0.08) !important;
        color: #00C853 !important;
    }}
</style>

<!-- Logo -->
<div class="logo-container">
    <img src="logo.png" alt="Cashin Ink Logo">
</div>

<h1>CASHIN INK</h1>
<h3>Miami — Premium Tattoo Studio</h3>
""", unsafe_allow_html=True)

# ============== CONFIG & SECRETS ==============
DB_PATH = os.path.join(os.getcwd(), "bookings.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY in Streamlit secrets.")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/?success=1")
CANCEL_URL  = st.secrets.get("STRIPE_CANCEL_URL", "https://your-app.streamlit.app/")
ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")

# ============== DATABASE ==============
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    name TEXT, age INTEGER, phone TEXT, email TEXT, description TEXT,
    date TEXT, time TEXT, start_dt TEXT, end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0, stripe_session_id TEXT,
    files TEXT, created_at TEXT
)
''')
conn.commit()

# ============== SESSION STATE ==============
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "appt_time_str" not in st.session_state:
    st.session_state.appt_time_str = "13:00"

# Capture time from HTML picker via query param
qp = st.experimental_get_query_params()
if "appt_time" in qp:
    candidate = qp["appt_time"][0]
    try:
        datetime.strptime(candidate, "%H:%M")
        st.session_state.appt_time_str = candidate
    except:
        pass
    st.experimental_rerun()

# ============== BOOKING FORM ==============
st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("2-hour session • Deposit locks your slot • Non-refundable")

with st.form("booking_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(305) 555-1234")
    with col2:
        age = st.number_input("Age*", min_value=18, max_value=100, value=25)
        email = st.text_input("Email*", placeholder="you@example.com")

    description = st.text_area("Tattoo Idea* (size, placement, style, references)", height=120)

    uploaded = st.file_uploader("Upload reference images (optional but recommended)", 
                               type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### Choose Your Date & Time")
    date_col, time_col = st.columns([2, 1])

    with date_col:
        appt_date = st.date_input("Date*", 
            min_value=datetime.today() + timedelta(days=1),
            max_value=datetime.today() + timedelta(days=90))
        if appt_date.weekday() == 6:
            st.error("Closed on Sundays — pick another day")
            st.stop()

    with time_col:
        st.markdown("#### Start Time")
        html_time = f"""
        <input type="time" id="timepicker" value="{st.session_state.appt_time_str}" step="3600"
               style="width:100%; height:50px; font-size:22px; background:#222; color:white; border:2px solid #00C853; border-radius:8px; text-align:center;">
        <script>
            document.getElementById('timepicker').addEventListener('change', function() {{
                const params = new URLSearchParams(window.location.search);
                params.set('appt_time', this.value);
                window.location.search = params.toString();
            }});
        </script>
        """
        components.html(html_time, height=80)

    # Parse selected time
    try:
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if not (12 <= appt_time.hour <= 20):
        st.error("Studio open 12:00 PM – 8:00 PM only")
        st.stop()

    display_time = appt_time.strftime("%I:%M %p").lstrip("0")
    st.success(f"Selected: **{appt_date.strftime('%A, %B %d')} at {display_time}**")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit** to secure my appointment")

    submit = st.form_submit_button("🔒 PAY DEPOSIT & LOCK MY SLOT")

    if submit:
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Please complete all fields and agree to the deposit policy.")
        else:
            local_start = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            local_end = local_start + timedelta(hours=2)
            utc_start = local_start.astimezone(pytz.UTC).isoformat()
            utc_end = local_end.astimezone(pytz.UTC).isoformat()

            conflict = c.execute("SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?", 
                                (utc_end, utc_start)).fetchone()
            if conflict:
                st.error(f"Slot just taken by {conflict[0]}. Please choose another time.")
                st.stop()

            booking_id = str(uuid.uuid4())
            folder = os.path.join(UPLOAD_DIR, booking_id)
            os.makedirs(folder, exist_ok=True)
            saved_paths = []
            for f in st.session_state.uploaded_files:
                path = os.path.join(folder, f.name)
                with open(path, "wb") as out:
                    out.write(f.getbuffer())
                saved_paths.append(path)

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Tattoo Deposit — {name} ({display_time}, {appt_date})"},
                        "unit_amount": 15000,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=SUCCESS_URL,
                cancel_url=CANCEL_URL,
                metadata={"booking_id": booking_id},
                customer_email=email,
            )

            c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                booking_id, name, age, phone, email, description,
                str(appt_date), display_time, utc_start, utc_end,
                0, session.id, ",".join(saved_paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Redirecting to secure payment...")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

# Success message
if st.experimental_get_query_params().get("success"):
    st.success("Payment Confirmed! Your slot is locked. Julio will reach out soon.")
    st.balloons()

# Admin view
with st.expander("Studio Only — Upcoming Bookings"):
    for row in c.execute("SELECT name, date, time, phone, deposit_paid FROM bookings ORDER BY date, time").fetchall():
        status = "PAID" if row[4] else "PENDING"
        color = "#00C853" if row[4] else "#FFA000"
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — <span style='color:{color}'>{status}</span>", 
                    unsafe_allow_html=True)

st.markdown("---")
st.caption("© 2025 Cashin Ink — Miami, FL | Built with ink, heart & code")