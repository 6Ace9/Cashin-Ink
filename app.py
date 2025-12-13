import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta, time
import uuid
import pytz
import streamlit.components.v1 as components
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from streamlit_calendar import calendar

st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="💉")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&display=swap');

    html, body, [class*="css"]  { height: 100%; margin: 0; padding: 0; }
    .stApp {
        background: url("https://cdn.jsdelivr.net/gh/6Ace9/Cashin-Ink@main/background.png")
                    no-repeat center center fixed;
        background-size: cover !important;
        min-height: 100vh;
        margin: 0; padding: 0;
        display: flex;
        flex-direction: column;
    }
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.86); z-index: -1;
    }

    /* GLASS CARD WITH GREEN GLOW */
    .main {
        background: rgba(22, 22, 28, 0.6);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 26px;
        border: 1px solid rgba(0, 200, 83, 0.4);
        box-shadow: 
            0 10px 40px rgba(0,0,0,0.7),
            0 0 30px rgba(0, 200, 83, 0.4),
            0 0 60px rgba(0, 255, 100, 0.25),
            inset 0 0 20px rgba(0, 255, 100, 0.1);
        margin:  60px auto 20px auto;
        max-width: 960px;
        padding: 25px;
        flex: 1;
    }

    @keyframes pulseGlow {
        from { box-shadow: 0 10px 40px rgba(0,0,0,0.7), 0 0 30px rgba(0,200,83,0.4), 0 0 60px rgba(0,255,100,0.25), inset 0 0 20px rgba(0,255,100,0.1); }
        to   { box-shadow: 0 10px 40px rgba(0,0,0,0.8), 0 0 40px rgba(0,200,83,0.6), 0 0 80px rgba(0,255,100,0.4), inset 0 0 30px rgba(0,255,100,0.15); }
    }

    @keyframes glow {
        from { filter: drop-shadow(0 0 20px #00C853); }
        to   { filter: drop-shadow(0 0 45px #00C853); }
    }
    .logo-glow { animation: glow 4s ease-in-out infinite alternate; border-radius: 20px; }

    .cashin-header {
        margin-top: 20px;
        color: #000000 !important;
        font-family: 'Dancing Script', cursive !important;
        font-weight: 700;
        font-size: 3.2rem !important;
        letter-spacing: 3px;
        animation: glow 4s ease-in-out infinite alternate;
        text-shadow: 
            0 0 10px #00C853,
            0 0 20px #00C853,
            0 0 40px #00ff6c,
            0 0 60px #00ff6c;
    }

    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stNumberInput>div>div>input,
    .stDateInput>div>div>input,
    .stSelectbox>div>div>select {
        background: rgba(40,40,45,0.9)!important;
        border: 1px solid #00C85340!important;
        border-radius: 14px!important;
        color: white!important;
        padding: 16px!important;
        font-size: 18px!important;
    }

    .stButton>button {
        background: linear-gradient(45deg,#00C853,#00ff6c)!important;
        color: black!important;
        font-weight: bold!important;
        border: none!important;
        border-radius: 18px!important;
        padding: 20px 60px!important;
        font-size: 22px!important;
        min-height: 76px!important;
        box-shadow: 0 10px 30px rgba(0,200,83,0.6)!important;
    }

    h1,h2,h3,h4 { color:#00ff88!important; text-align:center; font-weight:500; }

    /* KILL EVERYTHING AT BOTTOM — 100% GONE */
    footer, [data-testid="stFooter"], .css-1d391kg, .css-1v0mbdj { display:none!important; }
    .block-container { padding-bottom:0!important; margin-bottom:0!important; }
    section.main { margin-bottom:0!important; padding-bottom:0!important; }
    .stApp > div:last-child { padding-bottom:0!important; margin-bottom:0!important; }

    /* Calendar custom styling to match theme */
    .fc { background: rgba(30,30,35,0.8); border-radius: 16px; color: white; }
    .fc-theme-standard td, .fc-theme-standard th { border-color: #00C85340; }
    .fc-button-primary { background: #00C853 !important; border: none !important; }
    .fc-button-primary:hover { background: #00ff6c !important; }
    .fc-event { background: #ff4444; border: none; opacity: 0.9; }
</style>

<div style="text-align:center;padding:0px 0 15px 0; margin-top:-20px;">
    <img src="https://raw.githubusercontent.com/6Ace9/Cashin-Ink/refs/heads/main/logo.PNG"
         class="logo-glow" style="width:360px;height:auto;" loading="lazy">
    <h3 class="cashin-header">Cashin Ink</h3>
</div>

<div class="main">
""", unsafe_allow_html=True)

# ==================== CONFIG ====================
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/Los_Angeles")
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

ICLOUD_ENABLED = "ICLOUD_EMAIL" in st.secrets and "ICLOUD_APP_PASSWORD" in st.secrets
if ICLOUD_ENABLED:
    ICLOUD_EMAIL = st.secrets["ICLOUD_EMAIL"]
    ICLOUD_APP_PASSWORD = st.secrets["ICLOUD_APP_PASSWORD"]

BASE_URL = "https://cashin-ink.streamlit.app"
SUCCESS_URL = f"{BASE_URL}/?success=1&session_id={{CHECKOUT_SESSION_ID}}"
CANCEL_URL = BASE_URL

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
if "appt_date_str" not in st.session_state:
    st.session_state.appt_date_str = (datetime.now(STUDIO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
if "appt_start_time_str" not in st.session_state:
    st.session_state.appt_start_time_str = "13:00"
if "appt_end_time_str" not in st.session_state:
    st.session_state.appt_end_time_str = "15:00"

# ==================== SUCCESS HANDLING ====================
if st.query_params.get("success") == "1":
    session_id = st.query_params.get("session_id")
    
    if session_id:
        c.execute("SELECT name, email, date, time, files FROM bookings WHERE stripe_session_id = ? AND deposit_paid = 0", (session_id,))
        booking = c.fetchone()
        
        if booking:
            name, email, appt_date, appt_time, files = booking
            
            c.execute("UPDATE bookings SET deposit_paid = 1 WHERE stripe_session_id = ?", (session_id,))
            conn.commit()
            
            if ICLOUD_ENABLED and email:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = ICLOUD_EMAIL
                    msg['To'] = email
                    msg['Subject'] = "Cashin Ink — Your Appointment is Confirmed!"

                    body = f"""
Thank you {name}!

Your tattoo appointment has been successfully booked and your $150 deposit is confirmed.

📅 Date: {appt_date}
🕒 Time: {appt_time}

Julio will reach out within 24 hours to discuss your design and finalize details.

We can't wait to create something amazing with you!

— Cashin Ink Team
Covina, CA
                    """
                    msg.attach(MIMEText(body, 'plain'))

                    if files:
                        for file_path in files.split(","):
                            if file_path and os.path.exists(file_path):
                                with open(file_path, "rb") as attachment:
                                    part = MIMEBase('application', 'octet-stream')
                                    part.set_payload(attachment.read())
                                    encoders.encode_base64(part)
                                    part.add_header(
                                        'Content-Disposition',
                                        f'attachment; filename={os.path.basename(file_path)}'
                                    )
                                    msg.attach(part)

                    server = smtplib.SMTP('smtp.mail.me.com', 587)
                    server.starttls()
                    server.login(ICLOUD_EMAIL, ICLOUD_APP_PASSWORD)
                    server.sendmail(ICLOUD_EMAIL, email, msg.as_string())
                    server.quit()
                except Exception as e:
                    st.warning("Payment confirmed, but confirmation email failed to send. We'll still contact you soon!")

            st.balloons()
            st.success("Payment Confirmed! Your slot is officially locked. 🎉")
            st.info("Julio will contact you within 24 hours to discuss your tattoo. Thank you!")
        else:
            st.error("Invalid or already processed payment session.")
    else:
        st.error("No payment session found.")

    st.stop()

# ==================== AVAILABILITY CALENDAR ====================
st.markdown("### Check Availability")
c.execute("SELECT name, start_dt, end_dt FROM bookings WHERE deposit_paid = 1")
booked = c.fetchall()

events = []
for name, start_utc, end_utc in booked:
    start_local = pytz.UTC.localize(datetime.fromisoformat(start_utc)).astimezone(STUDIO_TZ)
    end_local = pytz.UTC.localize(datetime.fromisoformat(end_utc)).astimezone(STUDIO_TZ)
    events.append({
        "title": f"Booked – {name}",
        "start": start_local.isoformat(),
        "end": end_local.isoformat(),
        "backgroundColor": "#ff4444",
        "borderColor": "#ff4444",
        "textColor": "white"
    })

calendar_options = {
    "initialView": "timeGridWeek",
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
    },
    "slotMinTime": "12:00:00",
    "slotMaxTime": "20:00:00",
    "hiddenDays": [0],
    "height": "600px",
    "editable": False,
    "selectable": False,
    "validRange": {
        "start": (datetime.now(STUDIO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
    }
}

cal = calendar(events=events, options=calendar_options, key="availability_cal")
st.markdown("<small>Red blocks = booked appointments. Studio open 12 PM – 8 PM (closed Sundays).</small>", unsafe_allow_html=True)

# ==================== MAIN FORM ====================
st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("Non-refundable • Locks your slot")

with st.form("booking_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(213) 555-0192")
    with col2:
        age = st.number_input("Age*", min_value=18, max_value=100, value=25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style)", height=140)

    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded:
        st.session_state.uploaded_files = uploaded

    st.markdown("### Select Date & Time Slot")

    col_date, col_start, col_end = st.columns(3)

    # Date picker (unchanged)
    with col_date:
        st.markdown("<small style='color:#00ff88;display:block;text-align:center;margin-bottom:4px;font-weight:600;'>Date</small>", unsafe_allow_html=True)
        min_date = datetime.now(STUDIO_TZ).date() + timedelta(days=1)
        max_date = min_date + timedelta(days=90)
        try:
            default_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        except:
            default_date = min_date
        selected_date = st.date_input(
            "",
            value=default_date,
            min_value=min_date,
            max_value=max_date,
            key="appt_date_input"
        )
        st.session_state.appt_date_str = selected_date.strftime("%Y-%m-%d")

    # Generate 30-minute slots from 12:00 PM to 7:30 PM (to allow up to 8:00 PM end)
    time_options = []
    display_options = []
    start_hour = 12
    end_hour = 19  # up to 19:30 for end time up to 20:00
    for hour in range(start_hour, end_hour + 1):
        for minute in [0, 30]:
            t = time(hour % 24, minute)
            time_options.append(t)
            display_options.append(t.strftime("%-I:%M %p"))

    # Start Time picker - 12-hour AM/PM dropdown
    with col_start:
        st.markdown("<small style='color:#00ff88;display:block;text-align:center;margin-bottom:4px;font-weight:600;'>Start Time</small>", unsafe_allow_html=True)
        try:
            default_start = datetime.strptime(st.session_state.appt_start_time_str, "%H:%M").time()
            start_index = time_options.index(default_start) if default_start in time_options else 2  # default ~1:00 PM
        except:
            start_index = 2
        selected_start_display = st.selectbox(
            "",
            options=display_options,
            index=start_index,
            key="start_time_select"
        )
        selected_start_time = time_options[display_options.index(selected_start_display)]
        st.session_state.appt_start_time_str = selected_start_time.strftime("%H:%M")

    # End Time picker - 12-hour AM/PM dropdown
    with col_end:
        st.markdown("<small style='color:#00ff88;display:block;text-align:center;margin-bottom:4px;font-weight:600;'>End Time</small>", unsafe_allow_html=True)
        try:
            default_end = datetime.strptime(st.session_state.appt_end_time_str, "%H:%M").time()
            end_index = time_options.index(default_end) if default_end in time_options else 6  # default ~3:00 PM
        except:
            end_index = 6
        selected_end_display = st.selectbox(
            "",
            options=display_options,
            index=end_index,
            key="end_time_select"
        )
        selected_end_time = time_options[display_options.index(selected_end_display)]
        st.session_state.appt_end_time_str = selected_end_time.strftime("%H:%M")

    # Parse for validation
    try:
        appt_date = datetime.strptime(st.session_state.appt_date_str, "%Y-%m-%d").date()
        appt_start = selected_start_time
        appt_end = selected_end_time
    except:
        appt_date = (datetime.now(STUDIO_TZ) + timedelta(days=1)).date()
        appt_start = time(13, 0)
        appt_end = time(15, 0)

    # Validation feedback
    if appt_date.weekday() == 6:
        st.error("❌ Closed on Sundays — please choose another day")
    if appt_start.hour < 12 or appt_start.hour >= 20 or appt_end.hour <= 12 or appt_end.hour > 20:
        st.error("❌ Times must be within 12 PM – 8 PM")
    if appt_end <= appt_start:
        st.error("❌ End time must be after start time")
    if (datetime.combine(appt_date, appt_end) - datetime.combine(appt_date, appt_start)) < timedelta(minutes=30):
        st.error("❌ Minimum 30 minutes per appointment")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")

    _, center, _ = st.columns([1, 2.4, 1])
    with center:
        submit = st.form_submit_button("BOOK APPOINTMENT", use_container_width=True)

    if submit:
        if not all([name.strip(), phone.strip(), email.strip(), description.strip()]):
            st.error("Please fill all required fields")
            st.stop()
        if age < 18:
            st.error("Must be 18 or older")
            st.stop()
        if not agree:
            st.error("You must agree to the non-refundable deposit")
            st.stop()
        if appt_date.weekday() == 6:
            st.error("Cannot book on Sundays")
            st.stop()
        if appt_start.hour < 12 or appt_start.hour >= 20 or appt_end.hour <= 12 or appt_end.hour > 20:
            st.error("Times must be within studio hours")
            st.stop()
        if appt_end <= appt_start:
            st.error("End time must be after start time")
            st.stop()

        start_dt_local = STUDIO_TZ.localize(datetime.combine(appt_date, appt_start))
        end_dt_local = STUDIO_TZ.localize(datetime.combine(appt_date, appt_end))

        start_utc = start_dt_local.astimezone(pytz.UTC).isoformat()
        end_utc = end_dt_local.astimezone(pytz.UTC).isoformat()

        c.execute("""
            SELECT name FROM bookings 
            WHERE deposit_paid = 1 
            AND start_dt < ? AND end_dt > ?
        """, (end_utc, start_utc))
        conflict = c.fetchone()

        if conflict:
            st.error(f"❌ This time overlaps with an existing booking ({conflict[0]}). Please choose another slot.")
            st.stop()

        bid = str(uuid.uuid4())
        os.makedirs(f"{UPLOAD_DIR}/{bid}", exist_ok=True)
        saved_paths = []
        import secrets
        for f in st.session_state.uploaded_files:
            ext = os.path.splitext(f.name)[1].lower()
            safe_filename = f"{secrets.token_hex(8)}{ext}"
            path = f"{UPLOAD_DIR}/{bid}/{safe_filename}"
            with open(path, "wb") as out:
                out.write(f.getbuffer())
            saved_paths.append(path)

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
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={"booking_id": bid},
            customer_email=email
        )

        c.execute("""INSERT INTO bookings 
                     (id, name, age, phone, email, description, date, time, start_dt, end_dt, 
                      deposit_paid, stripe_session_id, files, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            bid, name, age, phone, email, description,
            str(appt_date), f"{appt_start.strftime('%-I:%M %p')} – {appt_end.strftime('%-I:%M %p')}",
            start_utc, end_utc,
            0, session.id, ",".join(saved_paths), datetime.utcnow().isoformat()
        ))
        conn.commit()

        st.session_state.uploaded_files = []
        st.session_state.appt_date_str = (datetime.now(STUDIO_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
        st.session_state.appt_start_time_str = "13:00"
        st.session_state.appt_end_time_str = "15:00"

        st.success("✅ Slot reserved! Redirecting to secure payment...")
        st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
        st.balloons()

# CLOSE CARD
st.markdown("</div>", unsafe_allow_html=True)

# WHITE FOOTER — EXACTLY AS ORIGINAL
st.markdown("""
<div style="text-align:center; color:white; font-size:16px; font-weight:500; letter-spacing:1px; padding:30px 0 0 0; margin:0;">
    © 2025 Cashin Ink — Covina, CA
</div>
""", unsafe_allow_html=True)

# RESTORE NATURAL SCROLL & FULL MOBILE COMPATIBILITY — FINAL FIX
st.markdown("""
<style>
    /* Core layout: flex column with full height */
    .stApp {
        display: flex !important;
        flex-direction: column !important;
        min-height: 100vh !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Main glass card takes available space but allows scrolling */
    .main {
        flex: 1 0 auto !important;  /* Critical: allows content to grow and scroll */
        margin: 60px auto 40px auto !important;  /* Reduced bottom margin */
    }

    /* Hide only Streamlit's default footer */
    footer, [data-testid="stFooter"] { display: none !important; }

    /* MOBILE FIXES */
    @media (max-width: 768px) {
        /* Add safe padding at bottom for address bar + ensure scrollability */
        .stApp {
            padding-bottom: 120px !important;   /* Space for mobile address bar */
        }

        /* Reduce top margin on mobile so logo + top of card is visible immediately */
        .main {
            margin-top: 20px !important;
            margin-bottom: 40px !important;
        }

        /* Ensure the entire page can scroll properly */
        html, body {
            height: auto !important;
            overflow-x: hidden !important;
        }
    }

    /* DESKTOP: Keep original spacing */
    @media (min-width: 769px) {
        .main {
            margin-top: 60px !important;
        }
    }
</style>
""", unsafe_allow_html=True)
