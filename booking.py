# app.py
import streamlit as st
from PIL import Image
import sqlite3
import os
import stripe
from io import BytesIO
from datetime import datetime, timedelta
import uuid
import base64
import pytz

# === Optional: ICS generation (no external lib required) ===
def create_ics(uid, title, description, start_dt, end_dt, organizer_email, attendee_email):
    """Return bytes of an .ics file for download."""
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_dt.strftime("%Y%m%dT%H%M%SZ")
    dtend = end_dt.strftime("%Y%m%dT%H%M%SZ")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Cashin Ink//Booking//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{title}
DESCRIPTION:{description}
ORGANIZER;CN=Cashin Ink:mailto:{organizer_email}
ATTENDEE;CN=Client;RSVP=TRUE:mailto:{attendee_email}
END:VEVENT
END:VCALENDAR
"""
    return ics.encode('utf-8')

# === DB setup ===
DB_PATH = "bookings.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute(
    """CREATE TABLE IF NOT EXISTS bookings (
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
        deposit_paid INTEGER,
        stripe_session_id TEXT,
        files TEXT,
        created_at TEXT
    )"""
)
conn.commit()

# === Streamlit page config & theme (black/white/green) ===
st.set_page_config(page_title="Cashin Ink — Bookings", layout="centered", page_icon="💉")
# custom styling
st.markdown(
    """
    <style>
    /* background & colors */
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    /* primary green accents */
    .css-1x8lxyo, .st-bk { color: #00C853; } /* some button text may vary across Streamlit versions */
    .stButton>button {
        background: linear-gradient(90deg,#00C853,#00C853);
        color: white;
        border-radius: 8px;
    }
    .stTextInput>div>input, .stTextArea>div>textarea, .stSelectbox>div>div {
        background: #111111;
        color: #fff;
        border-radius: 6px;
    }
    .upload-box { border: 2px dashed #00C853; padding: 10px; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# === Load assets (logo + background) ===
LOGO_PATH = "B57CEC91-3B05-4094-97F4-ED1C90DA0B9D.jpeg"  # provided by user
BG_PATH = "A5B0F3EA-FEAE-40AD-ACE9-9182CBA69EE0.jpeg"  # provided by user

def load_img(path):
    try:
        return Image.open(path)
    except Exception:
        return None

logo_img = load_img(LOGO_PATH)
bg_img = load_img(BG_PATH)

col1, col2 = st.columns([1,4])
with col1:
    if logo_img:
        st.image(logo_img, width=120)
with col2:
    st.markdown("<h1 style='color:white;margin-bottom:0'>Cashin Ink — Book Now</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:#AFAFAF;margin-top:0'>Owner: Julio Munoz</div>", unsafe_allow_html=True)

if bg_img:
    st.image(bg_img, use_column_width=True)

st.markdown("---")

# === Stripe init from secrets ===
secrets = st.secrets.get("general", {})
STRIPE_SECRET = secrets.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE = secrets.get("STRIPE_PUBLISHABLE_KEY", "")
SUCCESS_URL = secrets.get("STRIPE_SUCCESS_URL", "")
CANCEL_URL = secrets.get("STRIPE_CANCEL_URL", "")
ORGANIZER_EMAIL = secrets.get("ORGANIZER_EMAIL", "julio@cashinink.example")

if not STRIPE_SECRET or not STRIPE_PUBLISHABLE:
    st.warning("Stripe keys not configured in Streamlit secrets. Deposit flow will not work until you add them.")
else:
    stripe.api_key = STRIPE_SECRET

# === Booking form ===
st.header("Book an Appointment — $150 deposit required to lock in")
with st.form("booking_form", clear_on_submit=False):
    st.subheader("Client details")
    name = st.text_input("Full name", placeholder="Julio Munoz", max_chars=100)
    age = st.number_input("Age (must be 18+)", min_value=0, max_value=120, value=18)
    phone = st.text_input("Phone number", placeholder="555-555-5555")
    email = st.text_input("Email", placeholder="client@example.com")
    description = st.text_area("Description of what you want (style / size / placement / references)", height=120)
    st.markdown("**Upload images or reference files (Photos, PDFs). iPhone users: use the paperclip icon in the upload widget.**")
    uploaded_files = st.file_uploader("Add files", accept_multiple_files=True, type=['png','jpg','jpeg','pdf','heic','mp4'])
    st.markdown("---")
    st.subheader("Choose date & time")
    appt_date = st.date_input("Appointment Date", min_value=datetime.today().date())
    # simple time selection
    appt_time = st.time_input("Preferred Start Time", value=datetime.now().time().replace(second=0, microsecond=0))
    duration_hours = st.selectbox("Duration (hours)", [1, 1.5, 2, 2.5, 3, 4], index=2)
    agree = st.checkbox("I am 18 or older and agree to Cashin Ink policies")
    submit_btn = st.form_submit_button("Proceed to deposit ($150)")

if submit_btn:
    if not (name and phone and email and description):
        st.error("Please enter name, phone, email and a short description.")
    elif age < 18:
        st.error("You must be 18 or older to book.")
    elif not agree:
        st.error("You must confirm you are 18+ and accept policies.")
    else:
        # prepare data
        start_dt = datetime.combine(appt_date, appt_time)
        # assume local timezone for display; store as UTC
        local_tz = pytz.timezone("UTC")
        start_dt_utc = local_tz.localize(start_dt).astimezone(pytz.utc)
        end_dt_utc = start_dt_utc + timedelta(hours=float(duration_hours))
        booking_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        # Save uploaded files into ./uploads/<booking_id>/
        saved_files = []
        if uploaded_files:
            save_dir = os.path.join("uploads", booking_id)
            os.makedirs(save_dir, exist_ok=True)
            for up in uploaded_files:
                fname = up.name
                fpath = os.path.join(save_dir, fname)
                with open(fpath, "wb") as f:
                    f.write(up.getbuffer())
                saved_files.append(fpath)

        # Start Stripe Checkout (if configured)
        if STRIPE_SECRET:
            try:
                # Create a Checkout Session
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': f'Cashin Ink Deposit — {name} — {appt_date} {appt_time}',
                                'description': 'Deposit to lock tattoo appointment'
                            },
                            'unit_amount': 15000,  # $150.00 in cents
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=(SUCCESS_URL + f"&booking_id={booking_id}"),
                    cancel_url=CANCEL_URL,
                    metadata={
                        "booking_id": booking_id,
                        "client_name": name,
                        "client_email": email
                    },
                )
                # Write a provisional booking record with deposit_paid=0 and stripe_session_id
                c.execute(
                    "INSERT INTO bookings (id,name,age,phone,email,description,date,time,start_dt,end_dt,deposit_paid,stripe_session_id,files,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        booking_id, name, int(age), phone, email, description,
                        str(appt_date), str(appt_time), start_dt_utc.isoformat(), end_dt_utc.isoformat(),
                        0, checkout_session.id, ",".join(saved_files), created_at
                    )
                )
                conn.commit()
                st.success("Deposit required — redirecting to Stripe Checkout...")
                # Redirect by showing Checkout link button
                st.markdown(f"[Pay $150 deposit and confirm appointment]({checkout_session.url})")
                st.info("After payment you will be redirected back to our site. Please use the 'My Bookings' tab to view confirmation.")
            except Exception as e:
                st.error(f"Stripe error: {e}")
        else:
            st.warning("Stripe not configured — deposit cannot be taken. Booking saved as unpaid (not locked).")
            c.execute(
                "INSERT INTO bookings (id,name,age,phone,email,description,date,time,start_dt,end_dt,deposit_paid,stripe_session_id,files,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    booking_id, name, int(age), phone, email, description,
                    str(appt_date), str(appt_time), start_dt_utc.isoformat(), end_dt_utc.isoformat(),
                    0, None, ",".join(saved_files), created_at
                )
            )
            conn.commit()
            st.info("Booking saved locally but unpaid. No appointment will be locked until deposit is made.")

st.markdown("---")
st.header("My Bookings / Calendar")

# Query DB for upcoming bookings
rows = c.execute("SELECT id,name,email,date,time,start_dt,end_dt,deposit_paid,files,created_at FROM bookings ORDER BY start_dt").fetchall()
import pandas as pd

if rows:
    df = pd.DataFrame(rows, columns=["id","name","email","date","time","start_dt","end_dt","deposit_paid","files","created_at"])
    # show as list
    for idx, r in df.iterrows():
        paid = "Yes" if r.deposit_paid else "No"
        st.markdown(f"**{r['name']}** — {r['date']} {r['time']} — Deposit: {paid}")
        # Offer ICS download if paid
        try:
            start_dt = datetime.fromisoformat(r["start_dt"])
            end_dt = datetime.fromisoformat(r["end_dt"])
        except Exception:
            start_dt = None
            end_dt = None
        if r["deposit_paid"]:
            if start_dt:
                uid = r["id"] + "@cashinink"
                ics_bytes = create_ics(uid, f"Cashin Ink — Tattoo with {r['name']}", "See notes in your confirmation email.", start_dt, end_dt, ORGANIZER_EMAIL, r["email"])
                b64 = base64.b64encode(ics_bytes).decode()
                href = f"data:text/calendar;base64,{b64}"
                st.markdown(f"[Add to Apple Calendar / Download ICS]({href})")
        else:
            st.markdown("_No deposit yet — appointment not locked._")
        # show files
        if r["files"]:
            files_list = r["files"].split(",")
            st.markdown("References:")
            for fpath in files_list:
                if os.path.exists(fpath):
                    st.markdown(f"- {os.path.basename(fpath)}")
    # show calendar-ish view (simple)
    st.subheader("Upcoming (calendar view)")
    # create a simple month grid for the current month
    now = datetime.now()
    start_month = datetime(now.year, now.month, 1)
    end_month = (start_month + pd.DateOffset(months=1)) - pd.DateOffset(days=1)
    dates = pd.date_range(start_month, end_month)
    cal_df = pd.DataFrame({"date": dates})
    # mark counts
    cal_df["count"] = cal_df["date"].apply(lambda d: df[df["date"] == d.date().isoformat()].shape[0] if "date" in df else 0)
    # display as table
    st.table(cal_df[["date","count"]].head(14))
else:
    st.info("No bookings yet.")

# === Handle return after Stripe success (user lands back with booking_id param) ===
url_params = st.experimental_get_query_params()
if "checkout" in url_params and url_params["checkout"][0] == "success" and "booking_id" in url_params:
    booking_id = url_params["booking_id"][0]
    st.success("Payment completed — verifying...")
    if STRIPE_SECRET:
        # find the booking
        rec = c.execute("SELECT stripe_session_id,deposit_paid FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if rec:
            session_id, deposit_paid = rec
            if session_id:
                try:
                    sess = stripe.checkout.Session.retrieve(session_id)
                    payment_status = sess.payment_status
                    if payment_status == "paid":
                        # mark deposit_paid = 1
                        c.execute("UPDATE bookings SET deposit_paid=1 WHERE id=?", (booking_id,))
                        conn.commit()
                        st.success("Deposit confirmed. Appointment locked!")
                        # offer ICS download
                        rec2 = c.execute("SELECT name,email,start_dt,end_dt FROM bookings WHERE id=?", (booking_id,)).fetchone()
                        if rec2:
                            nm, eml, s_dt, e_dt = rec2
                            s_dt = datetime.fromisoformat(s_dt)
                            e_dt = datetime.fromisoformat(e_dt)
                            uid = booking_id + "@cashinink"
                            ics_bytes = create_ics(uid, f"Cashin Ink — Tattoo with {nm}", f"{nm} — appointment with Cashin Ink", s_dt, e_dt, ORGANIZER_EMAIL, eml)
                            b64 = base64.b64encode(ics_bytes).decode()
                            href = f"data:text/calendar;base64,{b64}"
                            st.markdown(f"[Add this appointment to your Apple Calendar / Download .ics]({href})")
                    else:
                        st.warning(f"Payment status: {payment_status}. If you were charged but status is not paid, contact support.")
                except Exception as e:
                    st.error(f"Could not verify Stripe session: {e}")
            else:
                st.error("No Stripe session associated with this booking.")
        else:
            st.error("Booking not found.")
    else:
        st.error("Stripe keys not configured; cannot verify payment here. If payment completed, update admin dashboard.")

st.markdown("---")
st.markdown("Cashin Ink • © Julio Munoz • Black · White · Green theme")