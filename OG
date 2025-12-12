# booking.py
# ==================== CASHIN INK — BOOKING APP V2 (FINAL, SLOT-MACHINE TIME PICKER) ====================
# VERSION: SLOT-MACHINE-12H-CALENDAR-V2-FINAL

import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import logging

# Optional caldav import (only used if iCloud creds are provided)
CALDAV_AVAILABLE = False
try:
    import caldav
    from caldav.elements import dav
    CALDAV_AVAILABLE = True
except Exception:
    # caldav may be missing; calendar integration will be disabled gracefully
    CALDAV_AVAILABLE = False

# ============== PAGE CONFIG (MUST BE FIRST STREAMLIT CALL) ==============
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")
st.warning("CASHIN INK — PRODUCTION READY V2")

# ============== CONFIG & SECRETS ==============
DB_PATH = os.path.join(os.getcwd(), "bookings.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

STUDIO_TZ = pytz.timezone("America/New_York")

# Required Stripe secret in Streamlit secrets
if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY in Streamlit secrets. Add it and reload.")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", "https://your-app.streamlit.app/?success=1")
CANCEL_URL  = st.secrets.get("STRIPE_CANCEL_URL", "https://your-app.streamlit.app/")
ORGANIZER_EMAIL = st.secrets.get("ORGANIZER_EMAIL", "julio@cashinink.com")

# iCloud calendar credentials are optional — only Julio's calendar needs them.
CALDAV_ENABLED = False
JULIO_CALENDAR = None
if CALDAV_AVAILABLE and "icloud" in st.secrets:
    icloud_cfg = st.secrets["icloud"]
    icloud_user = icloud_cfg.get("username")
    icloud_pass = icloud_cfg.get("app_password")
    if icloud_user and icloud_pass:
        try:
            cal_client = caldav.DAVClient(
                url="https://caldav.icloud.com/",
                username=icloud_user,
                password=icloud_pass
            )
            principal = cal_client.principal()
            calendars = principal.calendars()
            if calendars:
                JULIO_CALENDAR = calendars[0]
                CALDAV_ENABLED = True
                logging.info("CalDAV connected to Julio's calendar.")
            else:
                logging.warning("No calendars found for Julio's iCloud account.")
        except Exception as e:
            logging.error(f"CalDAV connection failed: {e}")
            CALDAV_ENABLED = False
    else:
        logging.info("iCloud credentials not set; skipping calendar integration.")
else:
    if not CALDAV_AVAILABLE:
        logging.info("caldav library not available; skipping calendar integration.")
    else:
        logging.info("No iCloud config found in secrets; skipping calendar integration.")

# ============== DATABASE ==============
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

# ============== STYLE ==============
st.markdown("""
<style>
.stApp { background:#000; color:#fff; }
h1, h2, h3 { color:#00C853 !important; }
.stButton>button { background:#00C853; color:black; font-weight:bold; border:none; padding:10px 14px; }
</style>
""", unsafe_allow_html=True)

st.title("CASHIN INK")
st.caption("Miami — Premium Tattoo Studio")
st.markdown("---")

# ============== SESSION STATE INITIALIZATION ==============
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
# store html time picker selected value (24h, "HH:MM")
if "appt_time_str" not in st.session_state:
    st.session_state.appt_time_str = "13:00"  # default 1:00 PM

# If user changed time via query param (from the HTML time picker), capture it
qp = st.experimental_get_query_params()
if "appt_time" in qp:
    candidate = qp.get("appt_time")[0]
    # basic validation HH:MM
    try:
        datetime.strptime(candidate, "%H:%M")
        st.session_state.appt_time_str = candidate
    except Exception:
        pass
    # remove appt_time from URL to avoid repeated reload/filtering
    # (rebuild base url without appt_time param)
    # We do a redirect to clean URL preserving other params
    base = st.runtime.scriptrunner.get_script_run_ctx()
    # simpler: perform a small client-side redirect to strip param
    st.experimental_rerun()

# ============== HELPER: create Apple Calendar event ==============
def create_apple_event(name, description, start_dt, end_dt):
    """Add event to Julio's Apple Calendar if CALDAV_ENABLED."""
    if not CALDAV_ENABLED or JULIO_CALENDAR is None:
        logging.info("Apple Calendar integration disabled or not configured.")
        return False
    try:
        start_utc = start_dt.astimezone(pytz.UTC)
        end_utc = end_dt.astimezone(pytz.UTC)
        event_data = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Tattoo Appointment - {name}
DESCRIPTION:{description}
DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}
END:VEVENT
END:VCALENDAR"""
        JULIO_CALENDAR.add_event(event_data)
        logging.info("Added event to Julio's Apple Calendar.")
        return True
    except Exception as e:
        logging.error(f"Failed to add event to Apple Calendar: {e}")
        return False

# ============== BOOKING FORM ==============
st.header("Book Your Session — $150 Deposit")
st.info("2-hour session • Deposit locks your slot • Non-refundable")

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
        # persist in session state so upload survives reruns
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
        # ====== SLOT-MACHINE STYLE TIME PICKER (EMBEDDED HTML) ======
        st.markdown("### Select Start Time (Slot Machine Style)")

        # Build HTML that sets window.location.search to include appt_time=HH:MM when changed.
        # This causes a reload and we capture the param above into session_state.appt_time_str
        html_time = f"""
        <input id="appt_time" type="time" step="60"
            style="
                width:160px;
                height:44px;
                font-size:20px;
                background-color:#444;
                color:white;
                border:none;
                border-radius:6px;
                text-align:center;
            ">
        <script>
            const input = document.getElementById('appt_time');
            // initialize value from Python (24-hour)
            input.value = "{st.session_state.appt_time_str}";
            input.addEventListener('change', function() {{
                const val = input.value; // "HH:MM"
                const searchParams = new URLSearchParams(window.location.search);
                searchParams.set('appt_time', val);
                // Preserve other params, set appt_time, reload
                const newUrl = window.location.pathname + '?' + searchParams.toString();
                window.location.href = newUrl;
            }});
        </script>
        """
        components.html(html_time, height=96)

    # After rendering the embedded picker, get the currently selected time from session_state
    try:
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except Exception:
        appt_time = datetime.strptime("13:00", "%H:%M").time()
        st.session_state.appt_time_str = "13:00"

    # Enforce studio hours (12:00 PM to 8:00 PM inclusive)
    if not (12 <= appt_time.hour <= 20):
        st.error("Studio open 12:00 PM – 8:00 PM only. Use the selector to choose a valid time.")
        st.stop()

    display_time = appt_time.strftime("%I:%M %p").lstrip("0")
    st.markdown(f"**Selected:** {appt_date.strftime('%A, %b %d')} at **{display_time}**")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit** to lock my spot")

    submit = st.form_submit_button("PAY DEPOSIT → LOCK MY SLOT")

    if submit:
        # Basic validation
        if not all([name.strip(), phone.strip(), email.strip(), description.strip()]):
            st.error("Please fill all required fields.")
        elif age < 18:
            st.error("Must be 18 or older.")
        elif not agree:
            st.error("You must agree to the deposit policy")
        else:
            # Build timezone-aware datetimes
            local_start = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            local_end = local_start + timedelta(hours=2)
            utc_start_iso = local_start.astimezone(pytz.UTC).isoformat()
            utc_end_iso = local_end.astimezone(pytz.UTC).isoformat()

            # Conflict check against paid bookings
            conflict = c.execute(
                "SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                (utc_end_iso, utc_start_iso)
            ).fetchone()
            if conflict:
                st.error(f"Sorry! This slot was just taken by {conflict[0]}. Please pick another time.")
                st.stop()

            # Save uploaded files to unique folder
            booking_id = str(uuid.uuid4())
            folder = os.path.join(UPLOAD_DIR, booking_id)
            os.makedirs(folder, exist_ok=True)
            saved_paths = []
            for file in st.session_state.uploaded_files:
                try:
                    path = os.path.join(folder, file.name)
                    with open(path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_paths.append(path)
                except Exception as e:
                    logging.error(f"Failed to save uploaded file {file.name}: {e}")

            # Create Stripe Checkout Session (OPTION A: clean success URL)
            try:
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
                    success_url=SUCCESS_URL,  # per Option A
                    cancel_url=CANCEL_URL,
                    metadata={"booking_id": booking_id},
                    customer_email=email,
                )
            except Exception as e:
                st.error(f"Failed to create Stripe session: {e}")
                logging.error(f"Stripe session create error: {e}")
                st.stop()

            # Persist booking as pending (deposit_paid = 0)
            try:
                c.execute("""
                    INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    booking_id, name, age, phone, email, description,
                    str(appt_date), display_time,
                    utc_start_iso,
                    utc_end_iso,
                    0, session.id, ",".join(saved_paths), datetime.utcnow().isoformat()
                ))
                conn.commit()
            except Exception as e:
                st.error(f"Database error saving booking: {e}")
                logging.error(f"DB insert error: {e}")
                st.stop()

            # Redirect to Stripe Checkout
            st.success("Taking you to secure payment...")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

# ============== SUCCESS FEEDBACK (user returns) ==============
params = st.experimental_get_query_params()
if "success" in params:
    # show a generic success message (webhook will mark deposit & add calendar even if they don't return)
    st.success("Payment Received! Your slot will be processed and Julio will be notified.")
    st.info("You’ll receive confirmation via email if provided.")
    st.balloons()

# ============== ADMIN: Upcoming bookings ==============
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

# ============== AFTER-DEPOSIT: Optionally add calendar when webhook or success page triggers it ==========
# NOTE: We don't add calendar events here automatically because booking is only "pending" until Stripe confirms.
# The Stripe webhook (recommended) should mark deposit_paid=1 and call create_apple_event(...) to add to calendar.
# If you prefer adding calendar on return (less reliable), uncomment the block below and handle carefully.

# if params.get("booking_id"):
#     bid = params.get("booking_id")[0]
#     row = c.execute("SELECT name, description, start_dt, end_dt FROM bookings WHERE id=?", (bid,)).fetchone()
#     if row:
#         name_val, desc_val, start_iso, end_iso = row
#         try:
#             # convert from iso strings to datetimes in studio tz
#             local_start = datetime.fromisoformat(start_iso).astimezone(STUDIO_TZ)
#             local_end = datetime.fromisoformat(end_iso).astimezone(STUDIO_TZ)
#             success = create_apple_event(name_val, desc_val, local_start, local_end)
#             if success:
#                 c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (bid,))
#                 conn.commit()
#                 st.success("Appointment added to Julio's Apple Calendar.")
#         except Exception as e:
#             logging.error(f"Failed to add calendar event on return: {e}")