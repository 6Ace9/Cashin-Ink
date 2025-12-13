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
from streamlit_calendar import calendar  # NEW IMPORT

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
    .stNumberInput>div>div>input {
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

    /* Enhanced Mobile fixes for calendar toolbar and layout */
    @media (max-width: 768px) {
        /* Stack toolbar vertically */
        .fc .fc-header-toolbar {
            flex-direction: column !important;
            gap: 10px !important;
            padding: 12px !important;
            text-align: center !important;
        }
        .fc .fc-toolbar-chunk {
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
            flex-wrap: wrap !important;
            gap: 6px !important;
        }

        /* Smaller buttons and abbreviated text on mobile */
        .fc .fc-button {
            padding: 6px 10px !important;
            font-size: 0.8rem !important;
            min-width: 40px !important;
        }
        .fc .fc-dayGridMonth-button { order: 1; }
        .fc .fc-timeGridWeek-button { order: 2; }
        .fc .fc-timeGridDay-button { order: 3; }

        /* Smaller title */
        .fc .fc-toolbar-title {
            font-size: 1.1rem !important;
            margin: 0 !important;
            width: 100% !important;
            order: 0 !important;
        }

        /* Horizontal scroll for timegrid */
        .fc .fc-scroller.fc-scroller-harness {
            overflow-x: auto !important;
        }
        .fc .fc-timegrid-col {
            min-width: 60px !important;
        }
    }
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
# ... (unchanged success handling code remains the same)

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
    "hiddenDays": [0],  # Hide Sundays
    "height": "auto",
    "expandRows": True,
    "editable": False,
    "selectable": False,
}

cal = calendar(events=events, options=calendar_options, key="availability_cal")
st.markdown("<small>Red blocks = booked appointments. Studio open 12 PM – 8 PM (closed Sundays).<br>On mobile: toolbar stacks vertically, buttons are smaller, and you can scroll horizontally to view all days.</small>", unsafe_allow_html=True)

# ==================== MAIN FORM ====================
# ... (rest of the code unchanged)

# (The rest of the code remains exactly as in the previous version)

# CLOSE CARD
st.markdown("</div>", unsafe_allow_html=True)

# WHITE FOOTER
st.markdown("""
<div style="text-align:center; color:white; font-size:16px; font-weight:500; letter-spacing:1px; padding:30px 0 0 0; margin:0;">
    © 2025 Cashin Ink — Covina, CA
</div>
""", unsafe_allow_html=True)

# RESTORE NATURAL SCROLL & BOTTOM GLOW
st.markdown("""
<style>
    .stApp {
        display: flex !important;
        flex-direction: column !important;
        min-height: 100vh !important;
    }
    .main {
        flex: 1 !important;
    }
    footer, [data-testid="stFooter"] { display: none !important; }
</style>
""", unsafe_allow_html=True)
