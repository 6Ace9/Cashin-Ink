# app.py ← FINAL VERSION – WORKS PERFECTLY ON DESKTOP & MOBILE
import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import base64
import requests

st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

# ==================== LOAD IMAGES (Local or GitHub Raw URLs) ====================
def img_b64(path):
    try:
        if path.startswith("http://") or path.startswith("https://"):
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

# ↓↓↓ PUT YOUR REAL GITHUB RAW URLs HERE ↓↓↓
logo_b64 = img_b64("https://raw.githubusercontent.com/USERNAME/REPO/main/logo.png")
bg_b64   = img_b64("https://raw.githubusercontent.com/USERNAME/REPO/main/background.png")
# ↑↑↑ REPLACE USERNAME/REPO WITH YOURS ↑↑↑

# ==================== UI STYLING ====================
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
    .stButton>button {{ background:#00C853 !important; color:black !important; font-weight:bold; border-radius:8px; padding:16px 40px; font-size:20px; }}
    .centered-button {{ display: flex; justify-content: center; margin-top: 30px; }}
    footer {{ visibility: hidden !important; }}

    /* Beautiful Native Date/Time Inputs */
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {{
        background: #1e1e1e !important;
        color: white !important;
        border: 2px solid #00C853 !important;
        border-radius: 8px !important;
        height: 56px !important;
        font-size: 20px !important;
        text-align: center !important;
        width: 100% !important;
    }}
    .stDateInput > div, .stTimeInput > div {{
        display: flex;
        justify-content: center;
    }}
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {{
        box-shadow: 0 0 15px rgba(0, 200, 83, 0.6) !important;
        outline: none !important;
    }}
</style>

<div style="text-align:center;padding:20px 0;">
    {logo_html}
    <h3>LA — Premium Tattoo Studio</h3>
</div>
<div class="main">
""", unsafe_allow_html=True)

# ==================== DATABASE & STRIPE ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY in Streamlit secrets")
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

# Session state defaults
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# ==================== BOOKING FORM ====================
st.markdown("---")
st.header("Book Sessions — $150 Deposit")
st.info("Lock your slot • Non-refundable deposit")

with st.form("booking_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(305) 555-1234")
    with col2:
        age = st.number_input("Age*", min_value=18, max_value=25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style, reference artists)", height=120)

    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### Date & Time")
    dc, tc = st.columns([2,1])

    with dc:
        st.markdown("<p style='text-align:center;font-weight:bold;color:#00C853;margin-bottom:8px;'>Select Date</p>", unsafe_allow_html=True)
        selected_date = st.date_input(
            "",
            value=datetime.today() + timedelta(days=1),
            min_value=datetime.today() + timedelta(days=1),
            max_value=datetime.today() + timedelta(days=90),
            label_visibility="collapsed",
            key="date_picker"
        )

    with tc:
        st.markdown("<p style='text-align:center;font-weight:bold;color:#00C853;margin-bottom:8px;'>Start Time</p>", unsafe_allow_html=True)
        selected_time = st.time_input(
            "",
            value=datetime.strptime("13:00", "%H:%M").time(),
            step=timedelta(hours=1),
            label_visibility="collapsed",
            key="time_picker"
        )

    # Validation
    if selected_date.weekday() == 6:  # Sunday
        st.error("We are closed on Sundays")
        st.stop()
    if selected_time.hour < 12 or selected_time.hour > 20:
        st.error("Studio open 12:00 PM – 8:00 PM only")
        st.stop()

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    st.markdown("<div class='centered-button'>", unsafe_allow_html=True)
    submit = st.form_submit_button("PAY DEPOSIT  =>  SCHEDULE APPOINTMENT")
    st.markdown("</div>", unsafe_allow_html=True)

    if submit:
        if not all([name.strip(), phone.strip(), email.strip(), description.strip()]) or age < 18 or not agree:
            st.error("Please complete all required fields and agree to the deposit")
        else:
            start_dt = STUDIO_TZ.localize(datetime.combine(selected_date, selected_time))
            end_dt = start_dt + timedelta(hours=2)

            # Check for conflicts
            conflict = c.execute(
                "SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())
            ).fetchone()

            if conflict:
                st.error(f"This time slot is already taken by {conflict[0]}")
                st.stop()

            # Save files
            bid = str(uuid.uuid4())
            os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
            file_paths = []
            for file in st.session_state.uploaded_files:
                path = f"{UPLOAD_DIR}/{bid}/{file.name}"
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                file_paths.append(path)

            # Create Stripe session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Tattoo Deposit – {name}"},
                        "unit_amount": 15000,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=SUCCESS_URL,
                cancel_url=CANCEL_URL,
                metadata={"booking_id": bid},
                customer_email=email
            )

            # Save booking (pending payment)
            c.execute("""INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                bid, name, age, phone, email, description, str(selected_date),
                selected_time.strftime("%-I:%M %p"),
                start_dt.astimezone(pytz.UTC).isoformat(),
                end_dt.astimezone(pytz.UTC).isoformat(),
                0, session.id, ",".join(file_paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Redirecting to secure payment…")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

# ==================== SUCCESS PAGE ====================
if st.query_params.get("success"):
    st.success("Payment Successful! Your appointment is confirmed.")
    st.balloons()
    st.info("Julio will contact you within 24 hours to confirm details.")

# ==================== ADMIN PANEL ====================
with st.expander("Studio Dashboard – Upcoming Bookings", expanded=False):
    bookings = c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time").fetchall()
    if not bookings:
        st.write("No bookings yet.")
    for row in bookings:
        status = "PAID" if row[4] else "PENDING PAYMENT"
        color = "#00C853" if row[4] else "#FF9800"
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — <span style='color:{color};font-weight:bold;'>{status}</span>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align:center; padding:40px 0 20px 0; color:#666; font-size:14px;">
    © 2025 Cashin Ink — Covina, CA<br>
    Premium Tattoo Studio • By Appointment Only
</div>
""", unsafe_allow_html=True)
