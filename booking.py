# ==================== CASHIN INK — BOOKING APP (12-HOUR SCROLL PICKER + Apple Calendar) ====================
# VERSION: SLOT-MACHINE-12H-CALENDAR-V1

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import caldav
from caldav.elements import dav

# ==================== PAGE CONFIG ====================
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")
st.warning("RUNNING VERSION: SLOT-MACHINE-12H-CALENDAR-V1")

# ==================== CONFIG ====================
DB_PATH = os.path.join(os.getcwd(), "bookings.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")

stripe.api_key = st.secrets.get("STRIPE_SECRET_KEY")
SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/")
CANCEL_URL  = st.secrets.get("STRIPE_CANCEL_URL",  "https://your-app.streamlit.app/")
ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")

# ==================== APPLE CALENDAR CONFIG (Julio) ====================
ICLOUD_USER = st.secrets["icloud"]["username"]
ICLOUD_PASS = st.secrets["icloud"]["app_password"]

# Connect to Julio's iCloud calendar
cal_client = caldav.DAVClient(
    url="https://caldav.icloud.com/",
    username=ICLOUD_USER,
    password=ICLOUD_PASS
)
principal = cal_client.principal()
JULIO_CALENDAR = principal.calendars()[0]  # default calendar

def create_apple_event(name, description, start_dt, end_dt):
    """Add event to Julio's Apple Calendar via CalDAV"""
    start_utc = start_dt.astimezone(pytz.UTC)
    end_utc = end_dt.astimezone(pytz.UTC)
    event_data = f"""
    BEGIN:VCALENDAR
    VERSION:2.0
    BEGIN:VEVENT
    SUMMARY:Tattoo Appointment - {name}
    DESCRIPTION:{description}
    DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}
    DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}
    END:VEVENT
    END:VCALENDAR
    """
    JULIO_CALENDAR.add_event(event_data)

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

if "appt_time_str" not in st.session_state:
    st.session_state.appt_time_str = "13:00"  # default 1:00 PM

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

    # ==================== SLOT-MACHINE STYLE TIME PICKER ====================
    st.subheader("Select Start Time (12-Hour Scroll)")
    time_html = f"""
    <input id="appt_time" type="time" step="60" 
           style="
               width:150px; 
               height:40px; 
               font-size:20px; 
               background-color:#444; 
               color:white; 
               border:none; 
               border-radius:5px;
               text-align:center;
           ">
    <script>
    const timeInput = document.getElementById("appt_time");
    timeInput.value = "{st.session_state.appt_time_str}";
    function sendTime() {{
        const val = timeInput.value;
        window.parent.postMessage({{type: 'time', value: val}}, "*");
    }}
    timeInput.addEventListener('change', sendTime);
    </script>
    """
    components.html(time_html, height=70)

    try:
        appt_time_24 = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
        appt_time = appt_time_24
        display_time = appt_time.strftime("%I:%M %p").lstrip("0")
    except:
        appt_time = datetime.strptime("13:00", "%H:%M").time()
        display_time = "1:00 PM"

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

            # Check for booking conflicts
            if c.execute(
                "SELECT 1 FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                (utc_end.isoformat(), utc_start.isoformat())
            ).fetchone():
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

            # Stripe checkout
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

# ==================== SUCCESS PAGE & APPLE CALENDAR INTEGRATION ====================
if st.query_params.get("booking_id"):
    bid = st.query_params["booking_id"]
    row = c.execute("SELECT name, description, start_dt, end_dt FROM bookings WHERE id=?", (bid,)).fetchone()
    if row:
        name, description, start_iso, end_iso = row
        c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
        conn.commit()

        # Convert to datetime objects
        local_start = datetime.fromisoformat(start_iso).astimezone(STUDIO_TZ)
        local_end = datetime.fromisoformat(end_iso).astimezone(STUDIO_TZ)

        # Add event to Julio's Apple Calendar
        try:
            create_apple_event(name, description, local_start, local_end)
            st.success(f"DEPOSIT CONFIRMED — Appointment added to Apple Calendar")
            st.balloons()
        except Exception as e:
            st.error(f"Payment confirmed but failed to add to Apple Calendar: {e}")

st.caption("© 2025 Cashin Ink — Miami, FL")