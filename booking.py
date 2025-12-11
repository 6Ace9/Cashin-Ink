# CASHIN INK — STREAMLIT BOOKING APP (FINAL PRODUCTION VERSION)
# Deploy this on: https://share.streamlit.io

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz

st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

# ==================== DATABASE ====================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY, name TEXT, age INTEGER, phone TEXT, email TEXT,
    description TEXT, date TEXT, time TEXT, start_dt TEXT, end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0, stripe_session_id TEXT, files TEXT, created_at TEXT
)
''')
conn.commit()

# ==================== STYLE ====================
st.markdown("""
<style>
.stApp { background:#000; color:#fff; }
h1,h2,h3 { color:#00C853 !important; }
.stButton>button { background:#00C853; color:black; font-weight:bold; border-radius:8px; padding:12px 24px; }
</style>
""", unsafe_allow_html=True)

st.title("CASHIN INK")
st.caption("Miami's Finest Ink")
st.markdown("---")

# ==================== BOOKING FORM ====================
st.header("Book Your Tattoo — $150 Deposit")
st.info("2-hour session • Deposit locks your spot • Non-refundable")

with st.form("booking_form"):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Full Name*", placeholder="Julio César")
        phone = st.text_input("Phone*", placeholder="(305) 555-0133")
    with c2:
        age = st.number_input("Age*", 18, 100, 18)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo idea — size, placement, style, references*", height=120)

    uploaded = st.file_uploader("Reference photos (highly recommended)", 
                               type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)

    st.markdown("### Choose Your Slot")
    dc, tc = st.columns([2,1])
    with dc:
        appt_date = st.date_input("Date*", min_value=datetime.today() + timedelta(days=1))
        if appt_date.weekday() == 6:
            st.error("Closed on Sundays")
            st.stop()
    with tc:
        default_time = datetime.strptime("13:00", "%H:%M").time()
        selected_time = st.time_input("Start Time*", value=default_time, step=3600)
        if selected_time.hour < 12 or selected_time.hour > 20:
            st.error("Open 12 PM – 8 PM only")
            st.stop()

    display_time = selected_time.strftime("%I:%M %p").lstrip("0")
    st.markdown(f"**Selected:** {appt_date.strftime('%A, %b %d')} at **{display_time}**")

    agree = st.checkbox("I agree to pay the **$150 non-refundable deposit** to lock my spot")
    submit = st.form_submit_button("PAY DEPOSIT → LOCK MY SLOT", type="primary")

    if submit:
        if not all([name, phone, email, description]):
            st.error("Fill all required fields")
        elif not agree:
            st.error("You must agree to the deposit")
        else:
            local_start = STUDIO_TZ.localize(datetime.combine(appt_date, selected_time))
            local_end = local_start + timedelta(hours=2)

            # Conflict check
            conflict = c.execute("""
                SELECT name FROM bookings 
                WHERE deposit_paid=1 
                AND start_dt < ? AND end_dt > ?
            """, (local_end.astimezone(pytz.UTC).isoformat(), 
                  local_start.astimezone(pytz.UTC).isoformat())).fetchone()

            if conflict:
                st.error(f"Slot just taken by {conflict[0]}. Pick another time.")
                st.stop()

            # Save files
            booking_id = str(uuid.uuid4())
            folder = os.path.join(UPLOAD_DIR, booking_id)
            os.makedirs(folder, exist_ok=True)
            paths = [os.path.join(folder, f.name) for f in uploaded or []]
            for f, path in zip(uploaded or [], paths):
                with open(path, "wb") as out:
                    out.write(f.getbuffer())

            # Create Stripe session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Tattoo Deposit — {name} ({display_time})"},
                        "unit_amount": 15000,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url="https://" + st.secrets["STREAMLIT_APP_URL"] + "/?paid=1",
                cancel_url="https://" + st.secrets["STREAMLIT_APP_URL"],
                metadata={"booking_id": booking_id},
                customer_email=email,
            )

            c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                booking_id, name, age, phone, email, description,
                str(appt_date), display_time,
                local_start.astimezone(pytz.UTC).isoformat(),
                local_end.astimezone(pytz.UTC).isoformat(),
                0, session.id, ",".join(paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Taking you to payment...")
            st.markdown(f"<meta http-equiv='refresh' content='2;url={session.url}'>", unsafe_allow_html=True)

# ==================== SUCCESS PAGE ====================
if st.query_params.get("paid"):
    st.balloons()
    st.success("DEPOSIT PAID — YOUR SLOT IS OFFICIALLY LOCKED!")
    st.info("You’ll get a confirmation email. The appointment will appear in Julio's calendar in <60 seconds.")
    st.markdown("### See you soon, legend.")

# ==================== ADMIN VIEW ====================
st.markdown("---")
with st.expander("Upcoming Bookings (Studio Only)"):
    for row in c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time"):
        status = "PAID" if row[4] else "PENDING PAYMENT"
        color = "#00C853" if row[4] else "#FF9800"
        st.markdown(f"**{row[0]}** — {row[1]} @ **{row[2]}** — {row[3]} — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

st.caption("© 2025 Cashin Ink — Miami, FL")