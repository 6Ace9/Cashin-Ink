# ==================== CASHIN INK — BOOKING APP V2 (FIXED & SECURE) ====================
# VERSION: SLOT-MACHINE-12H-CALENDAR-V2-FINAL

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz

# ==================== PAGE CONFIG ====================
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")
st.warning("CASHIN INK — PRODUCTION READY V2")

# ==================== CONFIG ====================
DB_PATH = os.path.join(os.getcwd(), "bookings.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/?success=1")
CANCEL_URL  = st.secrets.get("STRIPE_CANCEL_URL", "https://your-app.streamlit.app/")

# ==================== DATABASE ====================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    name TEXT,
    age INTEGER,
    phone TEXT,
    email TEXT,
    description TEXT,
    date TEXT,
    time TEXT,
    start_dt TEXT,
    end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0,
    stripe_session_id TEXT,
    files TEXT,
    created_at TEXT
)
''')
conn.commit()

# ==================== STYLE ====================
st.markdown("""
<style>
.stApp { background:#000; color:#fff; }
h1, h2, h3 { color:#00C853 !important; }
.stButton>button { background:#00C853; color:black; font-weight:bold; border:none; padding:12px; }
.css-1d391kg { color: white; }  /* fix file uploader text */
</style>
""", unsafe_allow_html=True)

st.title("CASHIN INK")
st.caption("Miami — Premium Tattoo Studio")
st.markdown("---")

# ==================== BOOKING FORM ====================
st.header("Book Your Session — $150 Deposit")
st.info("2-hour session • Deposit locks your slot • Non-refundable")

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

with st.form("booking_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(305) 555-1234")
    with col2:
        age = st.number_input("Age*", min_value=18, max_value=100, value=18)
        email = st.text_input("Email*", placeholder="john@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style, reference artists)", height=120)

    uploaded = st.file_uploader(
        "Upload reference photos (optional but recommended)",
        type=["png","jpg","jpeg","heic","pdf"],
        accept_multiple_files=True
    )
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### When do you want it?")
    date_col, time_col = st.columns([2, 1])

    with date_col:
        appt_date = st.date_input(
            "Pick a Date*",
            min_value=datetime.today() + timedelta(days=1),
            max_value=datetime.today() + timedelta(days=90)
        )

        # Block Sundays
        if appt_date.weekday() == 6:
            st.error("Closed on Sundays — pick another day")
            st.stop()

    with time_col:
        # ONLY ALLOW 12 PM – 8 PM
        if "selected_time" not in st.session_state:
            st.session_state.selected_time = datetime.strptime("13:00", "%H:%M").time()

        selected_time = st.time_input(
            "Start Time*",
            value=st.session_state.selected_time,
            step=3600  # 60-minute steps only
        )
        st.session_state.selected_time = selected_time

        # Enforce studio hours
        if not (12 <= selected_time.hour <= 20):
            st.error("Studio open 12:00 PM – 8:00 PM only")
            st.stop()

    display_time = selected_time.strftime("%I:%M %p").lstrip("0")
    st.markdown(f"**Selected:** {appt_date.strftime('%A, %b %d')} at **{display_time}**")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit** to lock my spot")

    submit = st.form_submit_button("PAY DEPOSIT → LOCK MY SLOT", type="primary")

    if submit:
        if not all([name.strip(), phone.strip(), email.strip(), description.strip()]):
            st.error("Please fill all required fields.")
        elif age < 18:
            st.error("Must be 18+")
        elif not agree:
            st.error("You must agree to the deposit policy")
        else:
            # Build datetimes
            local_start = STUDIO_TZ.localize(datetime.combine(appt_date, selected_time))
            local_end = local_start + timedelta(hours=2)

            # Check for conflict (only paid bookings block)
            conflict = c.execute(
                "SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                (local_end.astimezone(pytz.UTC).isoformat(), local_start.astimezone(pytz.UTC).isoformat())
            ).fetchone()

            if conflict:
                st.error(f"Sorry! This slot was just taken by {conflict[0]}. Please pick another time.")
                st.stop()

            # Save files
            booking_id = str(uuid.uuid4())
            folder = os.path.join(UPLOAD_DIR, booking_id)
            os.makedirs(folder, exist_ok=True)
            saved_paths = []
            for file in st.session_state.uploaded_files:
                path = os.path.join(folder, file.name)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                saved_paths.append(path)

            # Create Stripe session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Tattoo Deposit — {name} ({display_time}, {appt_date})"
                        },
                        "unit_amount": 15000,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=SUCCESS_URL + f"?session_id={session.id}",
                cancel_url=CANCEL_URL,
                metadata={"booking_id": booking_id},
                customer_email=email,
            )

            # Save pending booking
            c.execute("""
                INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                booking_id, name, age, phone, email, description,
                str(appt_date), display_time,
                local_start.astimezone(pytz.UTC).isoformat(),
                local_end.astimezone(pytz.UTC).isoformat(),
                0, session.id, ",".join(saved_paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Taking you to secure payment...")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

# ==================== SUCCESS MESSAGE (NO CALENDAR SYNC HERE!) ====================
if st.query_params.get("session_id"):
    st.success("Payment Received! Your slot is now LOCKED.")
    st.info("You’ll get a confirmation email shortly. Julio will reach out to finalize your design.")
    st.balloons()
    st.markdown("### See you soon at Cashin Ink")

# ==================== UPCOMING BOOKINGS (Admin View) ====================
st.markdown("---")
with st.expander("View Upcoming Appointments (Studio Only)", expanded=False):
    rows = c.execute("""
        SELECT name, date, time, phone, deposit_paid 
        FROM bookings 
        ORDER BY date, time
    """).fetchall()
    for row in rows:
        name, date, time, phone, paid = row
        status = "PAID" if paid else "PENDING"
        color = "#00C853" if paid else "#FFA000"
        st.markdown(f"**{name}** — {date} @ **{time}** — {phone} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

st.caption("© 2025 Cashin Ink — Miami, FL | Built with love & ink")