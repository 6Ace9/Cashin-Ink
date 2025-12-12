# app.py  ← Rename your file to app.py (or keep booking.py, doesn't matter)
import streamlit as st
import sqlite3
import os
import stripe
from datetime import datetime, timedelta
import uuid
import pytz
import streamlit.components.v1 as components
import base64

# ============== THIS MUST BE FIRST! ==============
st.set_page_config(page_title="Cashin Ink", layout="centered", page_icon="Tattoo")

# ============== LOAD IMAGES (100% WORKING) ==============
def img_to_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

logo_b64 = img_to_b64("logo.png")
bg_b64 = img_to_b64("background.png")

logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="display:block;margin:0 auto;width:340px;filter:drop-shadow(0 0 25px #00C853);">' \
            if logo_b64 else "<h1 style='color:#00C853;text-align:center;'>CASHIN INK</h1>"

bg_css = f"background:linear-gradient(rgba(0,0,0,0.88),rgba(0,0,0,0.88)),url('data:image/png;base64,{bg_b64}') center/cover no-repeat fixed;" \
         if bg_b64 else "background:#000;"

# ============== FULL CUSTOM STYLE + LOGO ==============
st.markdown(f"""
<style>
    .stApp {{ {bg_css} min-height:100vh; }}
    .main {{ background:rgba(0,0,0,0.5); padding:30px; border-radius:18px; max-width:900px; margin:20px auto; border:1px solid #00C85340; }}
    h1,h2,h3,h4 {{ color:#00C853 !important; text-align:center; }}
    .stButton>button {{ background:#00C853 !important; color:black !important; font-weight:bold; border-radius:8px; padding:14px 32px; font-size:18px; }}
    input[type="time"] {{ width:100% !important; max-width:170px; height:50px; font-size:20px; text-align:center; background:#111; color:white; border:2px solid #00C853; border-radius:8px; }}
    .stTextInput input, .stTextArea textarea {{ background:rgba(255,255,255,0.1)!important; color:white!important; border:1px solid #00C853!important; }}
</style>

<div style="text-align:center;padding:20px 0 10px;">
    {logo_html}
    <h3>Miami — Premium Tattoo Studio</h3>
</div>
<div class="main">
""", unsafe_allow_html=True)

# ============== YOUR FULL ORIGINAL LOGIC BELOW (unchanged) ==============
DB_PATH = "bookings.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
STUDIO_TZ = pytz.timezone("America/New_York")

if "STRIPE_SECRET_KEY" not in st.secrets:
    st.error("Missing STRIPE_SECRET_KEY in secrets")
    st.stop()
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

SUCCESS_URL = st.secrets.get("STRIPE_SUCCESS_URL", f"{st.secrets.get('BASE_URL', '')}/?success=1")
CANCEL_URL = st.secrets.get("STRIPE_CANCEL_URL", st.secrets.get("BASE_URL", ""))

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY, name TEXT, age INTEGER, phone TEXT, email TEXT, description TEXT,
    date TEXT, time TEXT, start_dt TEXT, end_dt TEXT,
    deposit_paid INTEGER DEFAULT 0, stripe_session_id TEXT, files TEXT, created_at TEXT
)''')
conn.commit()

if "uploaded_files" not in st.session_state: st.session_state.uploaded_files = []
if "appt_time_str" not in st.session_state: st.session_state.appt_time_str = "13:00"

# Time picker via query param
qp = st.experimental_get_query_params()
if "appt_time" in qp:
    t = qp["appt_time"][0]
    if len(t) == 5 and t[2] == ":":
        st.session_state.appt_time_str = t
    st.experimental_rerun()

st.markdown("---")
st.header("Book Your Session — $150 Deposit")
st.info("2-hour session • Deposit locks your slot • Non-refundable")

with st.form("booking_form"):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Full Name*", placeholder="John Doe")
        phone = st.text_input("Phone*", placeholder="(305) 555-1234")
    with c2:
        age = st.number_input("Age*", 18, 100, 25)
        email = st.text_input("Email*", placeholder="you@gmail.com")

    description = st.text_area("Tattoo Idea* (size, placement, style)", height=120)
    uploaded = st.file_uploader("Reference photos (optional)", type=["png","jpg","jpeg","heic","pdf"], accept_multiple_files=True)
    if uploaded: st.session_state.uploaded_files = uploaded

    st.markdown("### Date & Time")
    dc, tc = st.columns([2,1])
    with dc:
        appt_date = st.date_input("Date*", datetime.today()+timedelta(days=1), datetime.today()+timedelta(days=90))
        if appt_date.weekday() == 6:
            st.error("Closed on Sundays")
            st.stop()
    with tc:
        st.markdown("**Start Time**")
        components.html(f"""
        <input type="time" value="{st.session_state.appt_time_str}" step="3600">
        <script>
            document.querySelector('input[type="time"]').addEventListener('change', e => {{
                const p = new URLSearchParams(window.location.search);
                p.set('appt_time', e.target.value);
                window.location.search = p.toString();
            }});
        </script>
        """, height=70)

    try:
        appt_time = datetime.strptime(st.session_state.appt_time_str, "%H:%M").time()
    except:
        appt_time = datetime.strptime("13:00", "%H:%M").time()

    if appt_time.hour < 12 or appt_time.hour > 20:
        st.error("Open 12 PM – 8 PM only")
        st.stop()

    display_time = appt_time.strftime("%I:%M %p").lstrip("0")
    st.success(f"Selected: **{appt_date.strftime('%A, %B %d')} at {display_time}**")

    agree = st.checkbox("I agree to the **$150 non-refundable deposit**")
    submit = st.form_submit_button("PAY DEPOSIT → LOCK MY SLOT")

    if submit:
        if not all([name, phone, email, description]) or age < 18 or not agree:
            st.error("Complete all fields & agree")
        else:
            start_dt = STUDIO_TZ.localize(datetime.combine(appt_date, appt_time))
            end_dt = start_dt + timedelta(hours=2)

            conflict = c.execute("SELECT name FROM bookings WHERE deposit_paid=1 AND start_dt < ? AND end_dt > ?",
                               (end_dt.astimezone(pytz.UTC).isoformat(), start_dt.astimezone(pytz.UTC).isoformat())).fetchone()
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
                line_items=[{"price_data":{"currency":"usd","product_data":{"name":f"Deposit – {name}"},"unit_amount":15000},"quantity":1}],
                mode="payment",
                success_url=SUCCESS_URL,
                cancel_url=CANCEL_URL,
                metadata={"booking_id": bid},
                customer_email=email
            )

            c.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                bid, name, age, phone, email, description, str(appt_date), display_time,
                start_dt.astimezone(pytz.UTC).isoformat(), end_dt.astimezone(pytz.UTC).isoformat(),
                0, session.id, ",".join(paths), datetime.utcnow().isoformat()
            ))
            conn.commit()

            st.success("Redirecting to payment…")
            st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
            st.balloons()

if st.experimental_get_query_params().get("success"):
    st.success("Payment confirmed! Your slot is locked. Julio will contact you soon.")
    st.balloons()

with st.expander("Studio — Upcoming Bookings"):
    for row in c.execute("SELECT name,date,time,phone,deposit_paid FROM bookings ORDER BY date,time").fetchall():
        st.markdown(f"**{row[0]}** — {row[1]} @ {row[2]} — {row[3]} — {'PAID' if row[4] else 'PENDING'}", 
                    unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.caption("© 2025 Cashin Ink — Miami, FL")