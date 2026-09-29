import io
import hmac
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(page_title="BAN 517 Forecasting Decision Lab", page_icon="📈", layout="wide")

PRIMARY = "#003b5c"
TEAL = "#006c67"
LIGHT = "#f4fbfb"
GOLD = "#d9a441"
DATA_DIR = Path("data")
METHODS = ["Moving Average", "Exponential Smoothing", "ARIMA"]

st.markdown(
    f"""
    <style>
      .block-container {{max-width: 1080px; padding-top: 1.5rem; padding-bottom: 3rem;}}
      .hero {{background: linear-gradient(135deg, {PRIMARY} 0%, {TEAL} 58%, #00a6a6 100%);
              padding: 28px 30px; border-radius: 16px; color: white; margin-bottom: 18px;}}
      .hero h1 {{margin: 0 0 8px 0; color: white;}}
      .hero p {{margin: 0; font-size: 1.08rem;}}
      .callout {{background: {LIGHT}; border-left: 6px solid #008c95; padding: 14px 16px;
                border-radius: 10px; margin: 10px 0 18px 0;}}
      .warning {{background: #fffaf0; border-left: 6px solid {GOLD}; padding: 14px 16px;
                border-radius: 10px; margin: 10px 0 18px 0;}}
      .score {{background:#eef7ff; border:1px solid #c9e2f5; padding:14px 16px;
              border-radius:10px; margin:10px 0 18px 0;}}
    </style>
    <div class="hero">
      <div style="font-size:14px;color:#d7f4f2;font-weight:700;">BAN 517 · Supply Chain Analytics</div>
      <h1>Forecasting Decision Lab</h1>
      <p>Forecast with your assigned data. Lock your decision. Then see what actually happened.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def private_config():
    try:
        lab = st.secrets["lab"]
        datasets = st.secrets["datasets"]
        cfg = {
            "forecast_tolerance": float(lab.get("forecast_tolerance", 0.75)),
            "mad_tolerance": float(lab.get("mad_tolerance", 0.15)),
            "managerial_tolerance": float(lab.get("managerial_tolerance", 0.75)),
            "verification_salt": str(lab["verification_salt"]),
        }
        codes = sorted(list(datasets.keys()))
        if not codes:
            raise ValueError("No datasets configured")
        return cfg, datasets, codes
    except Exception:
        st.error(
            "Instructor setup is incomplete. Paste the supplied INSTRUCTOR_SECRETS.toml contents "
            "into Streamlit Community Cloud → App Settings → Secrets."
        )
        st.stop()


def dataset_for_student(student_id, codes):
    token = hashlib.sha256(student_id.strip().upper().encode("utf-8")).hexdigest()
    return codes[int(token[:12], 16) % len(codes)]


def load_dataset(code):
    path = DATA_DIR / f"{code}.csv"
    if not path.exists():
        st.error(f"Assigned dataset file is missing: {path}")
        st.stop()
    df = pd.read_csv(path, encoding="utf-8-sig")
    required = {"Year", "Month", "Quantity"}
    if not required.issubset(set(df.columns)):
        st.error(f"Dataset {code} must contain Year, Month, and Quantity columns.")
        st.stop()
    return df[["Year", "Month", "Quantity"]]


def close_num(value, correct, tolerance):
    return abs(float(value) - float(correct)) <= float(tolerance)


def grade_forecasting(ans, key, cfg):
    checks = []
    def add(label, ok, pts):
        checks.append({"Item": label, "Status": "Correct" if ok else "Incorrect", "Points": pts if ok else 0, "Max": pts})

    add("3-period moving-average forecast", close_num(ans["ma_forecast"], key["ma_forecast"], cfg["forecast_tolerance"]), 0.75)
    add("Moving-average MAD", close_num(ans["ma_mad"], key["ma_mad"], cfg["mad_tolerance"]), 0.75)
    add("Exponential-smoothing forecast", close_num(ans["es_forecast"], key["es_forecast"], cfg["forecast_tolerance"]), 0.75)
    add("Exponential-smoothing MAD", close_num(ans["es_mad"], key["es_mad"], cfg["mad_tolerance"]), 0.75)
    add("ARIMA p", int(ans["p"]) == int(key["p"]), 0.25)
    add("ARIMA d", int(ans["d"]) == int(key["d"]), 0.25)
    add("ARIMA q", int(ans["q"]) == int(key["q"]), 0.25)
    add("ARIMA next-period forecast", close_num(ans["arima_forecast"], key["arima_forecast"], cfg["forecast_tolerance"]), 1.0)
    add("ARIMA MAD", close_num(ans["arima_mad"], key["arima_mad"], cfg["mad_tolerance"]), 1.0)
    add("Method selected from MAD comparison", ans["selected_method"] == str(key["best_method"]), 1.25)
    return checks


def selected_forecast(ans):
    return {
        "Moving Average": float(ans["ma_forecast"]),
        "Exponential Smoothing": float(ans["es_forecast"]),
        "ARIMA": float(ans["arima_forecast"]),
    }[ans["selected_method"]]


def managerial_problem(forecast, actual, key):
    diff = float(actual) - float(forecast)
    if diff > 0.000001:
        shortage = diff
        ec = float(key["expedite_cost"])
        sc = float(key["shortage_cost"])
        cap = float(key["expedite_capacity"])
        expedite = min(shortage, cap) if ec < sc else 0.0
        unfilled = shortage - expedite
        total = expedite * ec + unfilled * sc
        prompt = (
            f"Your forecast was {forecast:.1f} units and actual demand was {actual:.1f} units, creating a "
            f"shortage of {shortage:.1f} units. {str(key['under_action']).capitalize()} costs ${ec:,.2f} per unit "
            f"and is limited to {cap:.0f} units. Each unit left unfilled has an estimated cost of ${sc:,.2f}. "
            "Calculate the cost-minimizing number of units to expedite, the units left unfilled, and the total cost."
        )
        return {
            "branch": "Underforecast",
            "difference": shortage,
            "prompt": prompt,
            "field1_label": "Units to expedite",
            "field2_label": "Units left unfilled",
            "correct1": expedite,
            "correct2": unfilled,
            "correct_cost": total,
        }
    if diff < -0.000001:
        excess = -diff
        cc = float(key["carry_cost"])
        oc = float(key["over_cost"])
        cap = float(key["carry_capacity"])
        carry = min(excess, cap) if cc < oc else 0.0
        alternate = excess - carry
        total = carry * cc + alternate * oc
        prompt = (
            f"Your forecast was {forecast:.1f} units and actual demand was {actual:.1f} units, leaving "
            f"{excess:.1f} excess units. You may {str(key['over_action']).lower()} at a cost of USD {cc:,.2f} per unit, "
            f"for at most {cap:.0f} units. Any excess units that are not carried must be handled by this option: "
            f"{str(key['over_alt']).lower()}, at a cost of USD {oc:,.2f} per unit. "
            "Calculate (1) the cost-minimizing quantity to carry, (2) the remaining quantity to handle using the stated "
            "alternative, and (3) the total cost."
        )
        return {
            "branch": "Overforecast",
            "difference": excess,
            "prompt": prompt,
            "field1_label": "Units to carry",
            "field2_label": f"Remaining units to {str(key['over_alt']).lower()}",
            "correct1": carry,
            "correct2": alternate,
            "correct_cost": total,
        }
    return {
        "branch": "Exact forecast",
        "difference": 0.0,
        "prompt": "Your selected forecast exactly matched actual demand. Enter zero for all three values below.",
        "field1_label": "Adjustment quantity",
        "field2_label": "Remaining quantity",
        "correct1": 0.0,
        "correct2": 0.0,
        "correct_cost": 0.0,
    }


def grade_managerial(student, problem, tol):
    return [
        {"Item": problem["field1_label"], "Status": "Correct" if close_num(student["value1"], problem["correct1"], tol) else "Incorrect", "Points": 0.75 if close_num(student["value1"], problem["correct1"], tol) else 0, "Max": 0.75},
        {"Item": problem["field2_label"], "Status": "Correct" if close_num(student["value2"], problem["correct2"], tol) else "Incorrect", "Points": 0.75 if close_num(student["value2"], problem["correct2"], tol) else 0, "Max": 0.75},
        {"Item": "Total cost", "Status": "Correct" if close_num(student["cost"], problem["correct_cost"], max(1.0, tol)) else "Incorrect", "Points": 1.5 if close_num(student["cost"], problem["correct_cost"], max(1.0, tol)) else 0, "Max": 1.5},
    ]


def verification_code(salt, payload):
    return hmac.new(salt.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:18].upper()


def make_pdf(name, sid, code, key, answers, forecast_checks, problem, manager_answers, manager_checks, salt):
    generated = datetime.now(timezone.utc)
    forecast_score = sum(x["Points"] for x in forecast_checks)
    manager_score = sum(x["Points"] for x in manager_checks)
    total = forecast_score + manager_score
    actual = float(key["actual"])
    sf = selected_forecast(answers)
    err = actual - sf
    payload = f"{sid}|{code}|{generated.isoformat()}|{answers}|{manager_answers}|{total}"
    vcode = verification_code(salt, payload)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=42, leftMargin=42, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenterTitle2", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor(PRIMARY)))
    story = [Paragraph("BAN 517 Forecasting Decision Lab", styles["CenterTitle2"]), Spacer(1, 8)]
    story += [
        Paragraph(f"<b>Student:</b> {name}", styles["BodyText"]),
        Paragraph(f"<b>Student ID:</b> {sid}", styles["BodyText"]),
        Paragraph(f"<b>Dataset:</b> {code} — {key['industry']}", styles["BodyText"]),
        Paragraph(f"<b>Generated (UTC):</b> {generated.strftime('%Y-%m-%d %H:%M:%S')}", styles["BodyText"]),
        Paragraph(f"<b>Verification code:</b> {vcode}", styles["BodyText"]), Spacer(1, 12),
    ]

    story.append(Paragraph("Forecasting Submission", styles["Heading2"]))
    rows = [
        ["Item", "Student Entry", "Result", "Points"],
        ["MA forecast", f"{answers['ma_forecast']:.2f}", forecast_checks[0]["Status"], f"{forecast_checks[0]['Points']}/5"],
        ["MA MAD", f"{answers['ma_mad']:.2f}", forecast_checks[1]["Status"], f"{forecast_checks[1]['Points']}/5"],
        ["ES forecast", f"{answers['es_forecast']:.2f}", forecast_checks[2]["Status"], f"{forecast_checks[2]['Points']}/5"],
        ["ES MAD", f"{answers['es_mad']:.2f}", forecast_checks[3]["Status"], f"{forecast_checks[3]['Points']}/5"],
        ["ARIMA order", f"({answers['p']},{answers['d']},{answers['q']})", 
         "Correct" if all(x['Status']=='Correct' for x in forecast_checks[4:7]) else "Check", f"{sum(x['Points'] for x in forecast_checks[4:7])}/6"],
        ["ARIMA forecast", f"{answers['arima_forecast']:.2f}", forecast_checks[7]["Status"], f"{forecast_checks[7]['Points']}/7"],
        ["ARIMA MAD", f"{answers['arima_mad']:.2f}", forecast_checks[8]["Status"], f"{forecast_checks[8]['Points']}/7"],
        ["Selected method", answers['selected_method'], forecast_checks[9]["Status"], f"{forecast_checks[9]['Points']}/5"],
    ]
    t = Table(rows, repeatRows=1, colWidths=[130, 150, 85, 55])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(PRIMARY)), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dfe5ec")),
        ("FONTSIZE", (0,0), (-1,-1), 8.5), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [t, Spacer(1, 12), Paragraph(f"<b>Forecasting score:</b> {forecast_score:.2f}/7.00", styles["BodyText"]), Spacer(1, 10)]

    story.append(Paragraph("Hidden Demand Reveal", styles["Heading2"]))
    story.append(Paragraph(f"Selected forecast: <b>{sf:.2f}</b> units", styles["BodyText"]))
    story.append(Paragraph(f"Actual demand: <b>{actual:.2f}</b> units", styles["BodyText"]))
    story.append(Paragraph(f"Forecast error (Actual - Forecast): <b>{err:.2f}</b> units", styles["BodyText"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Managerial Calculation", styles["Heading2"]))
    story.append(Paragraph(problem["prompt"], styles["BodyText"]))
    mrows = [
        ["Item", "Student Entry", "Result", "Points"],
        [problem["field1_label"], f"{manager_answers['value1']:.2f}", manager_checks[0]["Status"], f"{manager_checks[0]['Points']}/6"],
        [problem["field2_label"], f"{manager_answers['value2']:.2f}", manager_checks[1]["Status"], f"{manager_checks[1]['Points']}/6"],
        ["Total cost", f"${manager_answers['cost']:,.2f}", manager_checks[2]["Status"], f"{manager_checks[2]['Points']}/8"],
    ]
    mt = Table(mrows, repeatRows=1, colWidths=[180, 120, 85, 55])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(PRIMARY)), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dfe5ec")),
        ("FONTSIZE", (0,0), (-1,-1), 8.5), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [mt, Spacer(1, 12), Paragraph(f"<b>Managerial calculation score:</b> {manager_score:.2f}/3.00", styles["BodyText"])]
    story += [Spacer(1, 12), Paragraph(f"<b>Automated Streamlit score:</b> {total:.2f}/10.00", styles["Heading2"])]
    story.append(Paragraph("Submit this verified PDF together with your Excel workbook and the PDF of your completed Python notebook in Canvas.", styles["BodyText"]))
    doc.build(story)
    buf.seek(0)
    return buf.getvalue(), vcode, total


cfg, datasets, codes = private_config()

for key, default in {
    "started": False, "locked": False, "manager_submitted": False, "name": "", "sid": "", "dataset_code": "",
    "answers": None, "forecast_checks": None, "manager_answers": None, "manager_checks": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.subheader("Lab Status")
    if st.session_state.started:
        st.write(f"Dataset: **{st.session_state.dataset_code}**")
        if st.session_state.locked:
            st.success("Forecast locked")
    st.caption("Use the same browser session until your PDF is generated.")

if not st.session_state.started:
    st.markdown('<div class="callout"><b>Workflow:</b> Identify yourself → download your assigned dataset → complete the forecasting work outside Streamlit → return and enter your answers → lock → reveal actual demand → solve the managerial calculation → download the verified PDF.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Student name")
    with c2:
        sid = st.text_input("Student ID")
    if st.button("Get My Dataset", type="primary", disabled=not(name.strip() and sid.strip())):
        code = dataset_for_student(sid, codes)
        st.session_state.name = name.strip()
        st.session_state.sid = sid.strip()
        st.session_state.dataset_code = code
        st.session_state.started = True
        st.rerun()
    st.stop()

code = st.session_state.dataset_code
key = datasets[code]
df = load_dataset(code)

st.markdown(f"## Step 1 — Download Your Dataset")
st.write(f"**Assigned industry:** {key['industry']}  ")
st.write(f"**Dataset code:** `{code}`")
st.download_button(
    "Download Historical Demand CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name=f"BAN517_{code}_historical.csv",
    mime="text/csv",
    type="primary",
)
with st.expander("Preview assigned historical data"):
    st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown('<div class="warning"><b>Complete your forecasting analysis outside this app.</b> Use the 3-period moving average, exponential smoothing with α = 0.35, and the instructor-provided ARIMA notebook. Calculate MAD from the third period onward. Keep your Excel workbook and save your completed Python notebook as a PDF for Canvas submission.</div>', unsafe_allow_html=True)

st.markdown("## Step 2 — Enter and Lock Your Forecasting Results")
if not st.session_state.locked:
    c1, c2 = st.columns(2)
    with c1:
        ma_forecast = st.number_input("3-period moving-average forecast for the next period", min_value=0.0, step=0.1)
        ma_mad = st.number_input("Moving-average MAD", min_value=0.0, step=0.1)
        es_forecast = st.number_input("Exponential-smoothing forecast for the next period", min_value=0.0, step=0.1)
        es_mad = st.number_input("Exponential-smoothing MAD", min_value=0.0, step=0.1)
    with c2:
        st.write("**ARIMA model**")
        p = st.number_input("p", min_value=0, max_value=10, step=1)
        d = st.number_input("d", min_value=0, max_value=3, step=1)
        q = st.number_input("q", min_value=0, max_value=10, step=1)
        arima_forecast = st.number_input("ARIMA forecast for the next period", min_value=0.0, step=0.1)
        arima_mad = st.number_input("ARIMA MAD", min_value=0.0, step=0.1)
    selected_method = st.selectbox("Which method would you recommend based on your analysis?", METHODS)
    confirm = st.checkbox("I understand that locking my answers will reveal the hidden future demand.")
    ready = all(v > 0 for v in [ma_forecast, ma_mad, es_forecast, es_mad, arima_forecast, arima_mad]) and confirm
    if st.button("Grade, Lock, and Reveal Actual Demand", type="primary", disabled=not ready):
        answers = {
            "ma_forecast": float(ma_forecast), "ma_mad": float(ma_mad),
            "es_forecast": float(es_forecast), "es_mad": float(es_mad),
            "p": int(p), "d": int(d), "q": int(q),
            "arima_forecast": float(arima_forecast), "arima_mad": float(arima_mad),
            "selected_method": selected_method,
        }
        checks = grade_forecasting(answers, key, cfg)
        st.session_state.answers = answers
        st.session_state.forecast_checks = checks
        st.session_state.locked = True
        st.rerun()
    st.stop()

answers = st.session_state.answers
forecast_checks = st.session_state.forecast_checks
forecast_score = sum(x["Points"] for x in forecast_checks)
st.markdown('<div class="score"><b>Your forecasting entries have been locked.</b> The app reports which submitted components are correct, but it does not reveal the private answer key.</div>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(forecast_checks), use_container_width=True, hide_index=True)
st.metric("Forecasting score", f"{forecast_score:.2f} / 7.00")

actual = float(key["actual"])
sf = selected_forecast(answers)
error = actual - sf
st.markdown("## Step 3 — Hidden Demand Reveal")
c1, c2, c3 = st.columns(3)
c1.metric("Your selected forecast", f"{sf:,.1f}")
c2.metric("Actual demand", f"{actual:,.1f}")
c3.metric("Forecast error", f"{error:,.1f}")

problem = managerial_problem(sf, actual, key)
st.markdown("## Step 4 — Dataset-Specific Managerial Calculation")
st.info(problem["prompt"])

if not st.session_state.manager_submitted:
    v1 = st.number_input(problem["field1_label"], min_value=0.0, step=0.1)
    v2 = st.number_input(problem["field2_label"], min_value=0.0, step=0.1)
    cost = st.number_input("Total cost ($)", min_value=0.0, step=1.0)
    if st.button("Submit Managerial Calculation", type="primary"):
        mans = {"value1": float(v1), "value2": float(v2), "cost": float(cost)}
        mchecks = grade_managerial(mans, problem, cfg["managerial_tolerance"])
        st.session_state.manager_answers = mans
        st.session_state.manager_checks = mchecks
        st.session_state.manager_submitted = True
        st.rerun()
    st.stop()

manager_answers = st.session_state.manager_answers
manager_checks = st.session_state.manager_checks
manager_score = sum(x["Points"] for x in manager_checks)
st.dataframe(pd.DataFrame(manager_checks), use_container_width=True, hide_index=True)
st.metric("Managerial calculation score", f"{manager_score:.2f} / 3.00")

st.markdown("## Step 5 — Download Your Verified Report")
pdf_bytes, vcode, total = make_pdf(
    st.session_state.name, st.session_state.sid, code, key, answers, forecast_checks,
    problem, manager_answers, manager_checks, cfg["verification_salt"]
)
st.success(f"Automated Streamlit score: {total:.2f}/10.00")
st.caption(f"Verification code: {vcode}")
clean_sid = re.sub(r"[^A-Za-z0-9_-]", "_", st.session_state.sid)
st.download_button(
    "Download Verified Forecasting Lab PDF",
    data=pdf_bytes,
    file_name=f"BAN517_Forecasting_Lab_{clean_sid}.pdf",
    mime="application/pdf",
    type="primary",
)
st.markdown('<div class="callout"><b>Canvas submission:</b> Upload (1) this verified Streamlit PDF, (2) your Excel workbook, and (3) a PDF of your completed Python notebook.</div>', unsafe_allow_html=True)
