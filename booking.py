import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz

# ==================== PAGE CONFIG MUST BE FIRST ====================
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

# ==================== VERSION BANNER ====================
st.warning("RUNNING VERSION: FIXED-12H-V2")

# ==================== CONFIG ====================
DB_PATH = os.path.join(os.getcwd(), "bookings.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")

stripe.api_key = st.secrets.get("STRIPE_SECRET_KEY")
SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/")
CANCEL_URL  = st.secrets.get("STRIPE_CANCEL_URL",  "https://your-app.streamlit.app/")
ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")

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
h1,h2,h3 { color:#00C853 !important; }
.stButton>button { background:#00C853; color:black; font-weight:bold; border:none; }
</style>
""", unsafe_allow_html=True)

st.title("CASHIN INK")
st.caption("Miami — Tattoo Booking")
st.markdown("---")

# ==================== BOOKING FORM ====================
st.header("Book Your Tattoo — $150 Deposit Required")
st.info("2-hour session • Deposit locks your spot")

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

with st.form("booking_form"):
    name  = st.text_input("Full Name*")
    age   = st.number_input("Age*", 18, 100, 18)
    phone = st.text_input("Phone*")
    email = st.text_input("Email*")
    description = st.text_area("Tattoo idea (size, placement, style)*")

    uploaded = st.file_uploader(
        "Reference photos",
        type=["png","jpg","jpeg","heic","pdf"],
        accept_multiple_files=True
    )
    if uploaded:
        st.session_state.uploaded_files = uploaded

    appt_date = st.date_input("Choose Date*", min_value=datetime.today() + timedelta(days=1))

    # 12-HOUR TIME PICKER
    st.subheader("Start Time (AM/PM Only)")
    hours = [str(h) for h in range(1, 13)]
    minutes = ["00", "30"]
    ampm = ["AM", "PM"]
    colA, colB, colC = st.columns(3)
    hour = colA.selectbox("Hour", hours)
    minute = colB.selectbox("Minutes", minutes)
    ap = colC.selectbox("AM / PM", ampm)
    appt_time = datetime.strptime(f"{hour}:{minute} {ap}", "%I:%M %p").time()

    agree = st.checkbox("I agree to the $150 non-refundable deposit")
    submit = st.form_submit_button("Pay Deposit → Lock My Spot")

    if submit:
        if not all([name, phone, email, description]):
            st.error("Fill all required fields.")
        elif age < 18:
            st.error("Must be 18 or older.")
        elif not agree:
            st.error("You must accept the deposit agreement.")
        else:
            local_start = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            local_end = local_start + timedelta(hours=2)
            utc_start = local_start.astimezone(pytz.UTC)
            utc_end = local_end.astimezone(pytz.UTC)

            if c.execute("SELECT 1 FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                         (utc_end.isoformat(), utc_start.isoformat())).fetchone():
                st.error("Slot just taken — pick another time!")
                st.stop()

            booking_id = str(uuid.uuid4())
            folder = os.path.join(UPLOAD_DIR, booking_id)
            os.makedirs(folder, exist_ok=True)

            saved_files = []
            for f in st.session_state.uploaded_files or []:
                path = os.path.join(folder, f.name)
                with open(path, "wb") as out:
                    out.write(f.getbuffer())
                saved_files.append(path)

            display_time = appt_time.strftime("%I:%M %p").lstrip("0")

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Deposit – {name}"},
                        "unit_amount": 15000
                    },
                    "quantity": 1
                }],
                mode="payment",
                success_url=SUCCESS_URL + f"?booking_id={booking_id}",
                cancel_url=CANCEL_URL,
                metadata={"booking_id": booking_id},
            )

            c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                booking_id, name, age, phone, email, description,
                str(appt_date), display_time, utc_start.isoformat(), utc_end.isoformat(),
                0, session.id, ",".join(saved_files), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Redirecting to payment…")
            st.markdown(f"<meta http-equiv='refresh' content='2;url={session.url}'>", unsafe_allow_html=True)

# ==================== SHOW BOOKINGS ====================
st.markdown("---")
st.header("Upcoming Appointments")
for row in c.execute("SELECT name,date,time,deposit_paid FROM bookings ORDER BY date,time"):
    name, date, time, paid = row
    status = "PAID" if paid else "Pending"
    color = "#00C853" if paid else "#FF0000"
    st.markdown(f"**{name}** — {date} at **{time}** — <span style='color:{color}'>{status}</span>", unsafe_allow_html=True)

# ==================== SUCCESS PAGE ====================
if st.query_params.get("booking_id"):
    bid = st.query_params["booking_id"]
    row = c.execute("SELECT name,time FROM bookings WHERE id=?", (bid,)).fetchone()
    if row:
        name, time = row
        c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
        conn.commit()
        st.balloons()
        st.success(f"DEPOSIT CONFIRMED — Appointment at {time}")

st.caption("© 2025 Cashin Ink — Miami, FL")