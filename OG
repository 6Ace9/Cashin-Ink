# app.py ← FINAL: BUTTON PERFECTLY CENTERED ON MOBILE & DESKTOP + NO EXTRA SCROLL SPACE
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

st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="💉")

# ==================== IMAGE LOADER (GitHub + Local) ====================
def img_b64(path):
    try:
        if path.startswith("http"):
            data = requests.get(path, timeout=10).content
        else:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
            else:
                return None
        return base64.b64encode(data).decode()
    except:
        return None

# YOUR GITHUB RAW URLs HERE
logo_b64 = img_b64("https://raw.githubusercontent.com/USERNAME/REPO/main/logo.png")
bg_b64   = img_b64("https://raw.githubusercontent.com/USERNAME/REPO/main/background.png")

logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="display:block;margin:20px auto;width:340px;filter:drop-shadow(0 0 25px #00C853);">'
    if logo_b64 else "<h1 style='color:#00C853;text-align:center;'>CASHIN INK</h1>"
)

bg_css = (
    f"background:linear-gradient(rgba(0,0,0,0.88),rgba(0,0,0,0.88)),url('data:image/png;base64,{bg_b64}') center/cover no-repeat fixed;"
    if bg_b64 else "background:#000;"
)

st.markdown(f"""
<style>
    .stApp {{ {bg_css} min-height:100vh; margin:0; padding:0; }}
    .main {{ background:rgba(0,0,0,0.5); padding:30px; border-radius:18px; max-width:900px; margin:20px auto; border:1px solid #00C85340; }}
    h1,h2,h3,h4 {{ color:#00C853 !important; text-align:center; }}
    .stButton>button {{ 
        background:#00C853 !important; 
        color:black !important; 
        font-weight:bold; 
        border-radius:8px; 
        padding:18px 40px !important; 
        font-size:20px !important;
        height: auto !important;
    }}
    /* Force wide rectangular button with proper centering on ALL devices */
    .wide-centered-button {{
        display: flex;
        justify-content: center;
        margin-top: 30px;
        margin-bottom: 0;
    }}
    .wide-centered-button > div {{
        width: 100%;
        max-width: 600px;
    }}
    .wide-centered-button button {{
        width: 100% !important;
    }}
    /* Remove any extra bottom space when scrolling */
    .block-container {{
        padding-bottom: 0 !important;
        margin-bottom: 0 !important;
    }}
    footer {{ visibility: hidden !important; }}
    /* Hide Streamlit's default footer and any extra padding */
    .css-1d391kg, .css-1avcm0n {{ display: none !important; }}
</style>

<div style="text-align:center;padding:20px 0;">
    {logo_html}
    <h3>LA — Premium Tattoo Studio</h3>
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
                   style="background:#1e1e1e;color:white;border:2px solid #00C853;border-radius:8px;
                          height:56px;width:220px;font-size:20px;text-align:center;">
        </div>
        <script>
            const dateInput = document.getElementById('datePicker');
            dateInput.removeAttribute('readonly');
            dateInput.showPicker && dateInput.addEventListener('click', () => dateInput.showPicker());
        </script>
        """, height=180)

    with tc:
        st.markdown("**Start Time**")
        components.html(f"""
        <div style="display:flex;justify-content:center;align-items:center;height:140px;">
            <input type="time" id="timePicker" value="{st.session_state.appt_time_str}" step="3600"
                   style="background:#1e1e1e;color:white;border:2px solid #00C853;border-radius:8px;
                          height:56px;width:180px;font-size:22px;text-align:center;">
        </div>
        <script>
            const timeInput = document.getElementById('timePicker');
            timeInput.removeAttribute('readonly');
            timeInput.showPicker && timeInput.addEventListener('click', () => timeInput.showPicker());
        </script>
        """, height=180)

    components.html(f"""
    <script>
        const dateInput = document.getElementById('datePicker');
        const timeInput = document.getElementById('timePicker');

        dateInput.addEventListener('change', function() {{
            parent.streamlit.setComponentValue({{date: this.value}});
        }});
        timeInput.addEventListener('change', function() {{
            parent.streamlit.setComponentValue({{time: this.value}});
        }});
    </script>
    """, height=0)

    picker_value = st.session_state.get("streamlit_component_value", {})
    if isinstance(picker_value, dict):
        if picker_value.get("date"):
            st.session_state.appt_date_str = picker_value["date"]
        if picker_value.get("time"):
            st.session_state.appt_time_str = picker_value["time"]

    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_date = (datetime.today() + timedelta(days=1)).date()
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if appt_date.weekday() == 6:
        st.error("Closed on Sundays — please choose another date")
    if appt_time.hour < 12 or appt_time.hour > 20:
        st.error("Open 12 PM – 8 PM only — please adjust time")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    # FINAL: WIDE, RECTANGULAR, PERFECTLY CENTERED BUTTON ON MOBILE & DESKTOP
    st.markdown("<div class='wide-centered-button'><div>", unsafe_allow_html=True)
    submit = st.form_submit_button("PAY DEPOSIT  =>  SCHEDULE APPOINTMENT")
    st.markdown("</div></div>", unsafe_allow_html=True)

    if submit:
        if appt_date.weekday() == 6:
            st.error("Closed on Sundays")
            st.stop()
        if appt_time.hour < 12 or appt_time.hour > 20:
            st.error("Open 12 PM – 8 PM only")
            st.stop()
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Complete all fields & agree")
            st.stop()

        start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
        end_dt = start_dt + timedelta(hours=2)

        conflict = c.execute(
            "SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
            (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())
        ).fetchone()

        if conflict:
            st.error(f"Slot taken by {conflict[0]}")
            st.stop()

        bid = str(uuid.uuid4())
        os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
        paths = []
        for f in st.session_state.uploaded_files:
            p = f"{UPLOAD_DIR}/{bid}/{f.name}"
            with open(p, "wb") as out:
                out.write(f.getbuffer())
            paths.append(p)

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

        st.success("Taking you to secure payment…")
        st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
        st.balloons()

# Success message
if st.query_params.get("success"):
    st.success("Payment confirmed! Your slot is locked. Julio will contact you soon.")
    st.balloons()

with st.expander("Studio — Upcoming Bookings"):
    for row in c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time").fetchall():
        status = "PAID" if row[4] else "PENDING"
        color = "#00C853" if row[4] else "#FF9800"
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center; padding:20px 0 30px 0; color:#888; font-size:14px;">
    © 2025 Cashin Ink — Covina, CA
</div>
""", unsafe_allow_html=True)
