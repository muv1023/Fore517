import io
import hashlib
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

st.set_page_config(page_title="BAN 517 Forecasting Decision Lab", page_icon="📈", layout="wide")

PRIMARY = "#003b5c"
TEAL = "#006c67"
LIGHT = "#f4fbfb"
GOLD = "#d9a441"

st.markdown(
    f"""
    <style>
      .block-container {{max-width: 1100px; padding-top: 1.5rem; padding-bottom: 3rem;}}
      .hero {{background: linear-gradient(135deg, {PRIMARY} 0%, {TEAL} 58%, #00a6a6 100%);
              padding: 28px 30px; border-radius: 16px; color: white; margin-bottom: 18px;}}
      .hero h1 {{margin: 0 0 8px 0; color: white;}}
      .hero p {{margin: 0; font-size: 1.08rem;}}
      .callout {{background: {LIGHT}; border-left: 6px solid #008c95; padding: 14px 16px;
                border-radius: 10px; margin: 10px 0 18px 0;}}
      .warning {{background: #fffaf0; border-left: 6px solid {GOLD}; padding: 14px 16px;
                border-radius: 10px; margin: 10px 0 18px 0;}}
      .small {{font-size: 0.9rem; color: #52616b;}}
    </style>
    <div class="hero">
      <div style="font-size:14px;color:#d7f4f2;font-weight:700;">BAN 517 · Supply Chain Analytics</div>
      <h1>Forecasting Decision Lab</h1>
      <p>Forecast first. Reveal actual demand second. Learn from the error.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

HISTORY_FILE = "data/forecast_history.csv"

@st.cache_data
def load_history():
    df = pd.read_csv(HISTORY_FILE)
    df["Period"] = pd.to_datetime(df["Period"])
    return df


def load_private_config():
    try:
        cfg = st.secrets["forecast_lab"]
        labels = list(cfg["future_labels"])
        actuals = [float(x) for x in cfg["actuals"]]
        under_cost = float(cfg.get("underforecast_cost", 10.0))
        over_cost = float(cfg.get("overforecast_cost", 3.0))
    except Exception:
        st.error(
            "Instructor setup is incomplete. Add the [forecast_lab] values to Streamlit Secrets before using the lab."
        )
        st.stop()
    if len(labels) != len(actuals) or len(actuals) == 0:
        st.error("The future_labels and actuals entries in Streamlit Secrets must have the same non-zero length.")
        st.stop()
    return labels, actuals, under_cost, over_cost


def initialize_state(round_count):
    defaults = {
        "student_name": "",
        "student_id": "",
        "started": False,
        "current_round": 0,
        "records": [],
        "locked": False,
        "post_decision_saved": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state.current_round >= round_count:
        st.session_state.current_round = round_count


def reset_lab():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def abs_error(forecast, actual):
    return abs(float(actual) - float(forecast))


def business_cost(forecast, actual, under_cost, over_cost):
    diff = float(actual) - float(forecast)
    if diff > 0:
        return diff * under_cost
    return abs(diff) * over_cost


def make_report(name, student_id, records, under_cost, over_cost):
    generated = datetime.now(timezone.utc)
    payload = f"{student_id}|{generated.isoformat()}|{records}".encode("utf-8")
    code = hashlib.sha256(payload).hexdigest()[:16].upper()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenterTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor(PRIMARY)))
    story = []
    story.append(Paragraph("BAN 517 Forecasting Decision Lab", styles["CenterTitle"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Student:</b> {name}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Student ID:</b> {student_id}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Generated (UTC):</b> {generated.strftime('%Y-%m-%d %H:%M:%S')}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Verification code:</b> {code}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    table_data = [["Round", "Period", "Actual", "MA", "ES", "ARIMA", "Selected", "Method"]]
    for r in records:
        table_data.append([
            r["round"], r["period"], f'{r["actual"]:.0f}', f'{r["ma"]:.1f}', f'{r["es"]:.1f}',
            f'{r["arima"]:.1f}', f'{r["selected_forecast"]:.1f}', r["selected_method"]
        ])
    t = Table(table_data, repeatRows=1, colWidths=[34, 62, 45, 45, 45, 48, 52, 72])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(PRIMARY)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dfe5ec")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-2,-1), "CENTER"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    df = pd.DataFrame(records)
    summary = []
    for label, col in [("Moving Average", "ma"), ("Exponential Smoothing", "es"), ("ARIMA", "arima")]:
        mad = (df[col] - df["actual"]).abs().mean()
        cost = sum(business_cost(f, a, under_cost, over_cost) for f, a in zip(df[col], df["actual"]))
        summary.append([label, f"{mad:.2f}", f"${cost:,.2f}"])
    selected_mad = (df["selected_forecast"] - df["actual"]).abs().mean()
    selected_cost = sum(business_cost(f, a, under_cost, over_cost) for f, a in zip(df["selected_forecast"], df["actual"]))
    summary.append(["Student-selected forecasts", f"{selected_mad:.2f}", f"${selected_cost:,.2f}"])

    story.append(Paragraph("Performance Summary", styles["Heading2"]))
    sdata = [["Approach", "MAD", "Business Cost"]] + summary
    s = Table(sdata, repeatRows=1, colWidths=[210, 80, 100])
    s.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(PRIMARY)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dfe5ec")),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(s)
    story.append(PageBreak())
    story.append(Paragraph("Round-by-Round Decisions", styles["Heading2"]))
    for r in records:
        story.append(Paragraph(f"<b>Round {r['round']} — {r['period']}</b>", styles["BodyText"]))
        story.append(Paragraph(f"Initial rationale: {r['rationale']}", styles["BodyText"]))
        story.append(Paragraph(f"After reveal: {r.get('next_action', '')}", styles["BodyText"]))
        story.append(Paragraph(f"Reflection: {r.get('reflection', '')}", styles["BodyText"]))
        story.append(Spacer(1, 8))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue(), code, generated


history = load_history()
future_labels, future_actuals, under_cost, over_cost = load_private_config()
initialize_state(len(future_actuals))

with st.sidebar:
    st.subheader("Lab Controls")
    st.caption("Your work is stored in this browser session until you finish or reset the lab.")
    if st.button("Reset Lab", type="secondary"):
        reset_lab()

if not st.session_state.started:
    st.markdown(
        '<div class="callout"><b>How this works:</b> You will forecast one hidden period at a time. '
        'After you lock a forecast, actual demand is revealed and your errors are calculated. ' 'Then you decide whether to keep or change your approach for the next round.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Student name")
    with c2:
        sid = st.text_input("Student ID")
    st.markdown("### Before you begin")
    st.write("- Use the historical data shown in the lab.")
    st.write("- Calculate forecasts using the required methods outside the app (Excel, Python, or approved AI support).")
    st.write("- Enter and lock your forecasts before actual demand is revealed.")
    st.write("- After each reveal, inspect the error and decide whether your approach should change.")
    if st.button("Start Forecasting Lab", type="primary", disabled=not (name.strip() and sid.strip())):
        st.session_state.student_name = name.strip()
        st.session_state.student_id = sid.strip()
        st.session_state.started = True
        st.rerun()
    st.stop()

round_idx = st.session_state.current_round
records = st.session_state.records

if round_idx < len(future_actuals):
    revealed_rows = []
    for i, r in enumerate(records):
        revealed_rows.append({"Period": pd.to_datetime(future_labels[i]), "Demand": r["actual"]})
    visible = pd.concat([history, pd.DataFrame(revealed_rows)], ignore_index=True) if revealed_rows else history.copy()
    visible = visible.sort_values("Period")

    st.progress(round_idx / len(future_actuals), text=f"Round {round_idx + 1} of {len(future_actuals)}")
    st.markdown(f"## Forecast Round {round_idx + 1}: {future_labels[round_idx]}")
    st.markdown(
        '<div class="callout"><b>Information set:</b> Only the demand observations shown below are currently known. '
        'The next actual value remains hidden until you lock your forecasts.</div>',
        unsafe_allow_html=True,
    )

    chart_df = visible.set_index("Period")[["Demand"]]
    st.line_chart(chart_df, height=300)
    with st.expander("View historical demand table"):
        show = visible.copy()
        show["Period"] = show["Period"].dt.strftime("%Y-%m")
        st.dataframe(show, use_container_width=True, hide_index=True)

    if not st.session_state.locked:
        st.markdown("### Enter your forecasts")
        c1, c2, c3 = st.columns(3)
        with c1:
            ma = st.number_input("3-period moving average", min_value=0.0, step=1.0, key=f"ma_{round_idx}")
        with c2:
            es = st.number_input("Exponential smoothing (α = 0.35)", min_value=0.0, step=1.0, key=f"es_{round_idx}")
        with c3:
            arima = st.number_input("ARIMA forecast", min_value=0.0, step=1.0, key=f"arima_{round_idx}")

        selected_method = st.selectbox(
            "Which method would you use for this period?",
            ["Moving Average", "Exponential Smoothing", "ARIMA", "Other / Adjusted Forecast"],
            key=f"method_{round_idx}",
        )
        default_selected = {"Moving Average": ma, "Exponential Smoothing": es, "ARIMA": arima}.get(selected_method, 0.0)
        selected_forecast = st.number_input(
            "Forecast you are committing to for the supply chain decision",
            min_value=0.0,
            value=float(default_selected),
            step=1.0,
            key=f"selected_{round_idx}",
        )
        rationale = st.text_area(
            "Briefly explain why you selected this forecast before seeing actual demand.",
            key=f"rationale_{round_idx}",
            max_chars=800,
        )
        ready = all(x > 0 for x in [ma, es, arima, selected_forecast]) and len(rationale.strip()) >= 10
        if st.button("Lock Forecast and Reveal Actual Demand", type="primary", disabled=not ready):
            actual = float(future_actuals[round_idx])
            rec = {
                "round": round_idx + 1,
                "period": future_labels[round_idx],
                "ma": float(ma),
                "es": float(es),
                "arima": float(arima),
                "selected_method": selected_method,
                "selected_forecast": float(selected_forecast),
                "rationale": rationale.strip(),
                "actual": actual,
            }
            st.session_state.records.append(rec)
            st.session_state.locked = True
            st.rerun()

    else:
        rec = st.session_state.records[-1]
        actual = rec["actual"]
        st.success(f"Actual demand for {rec['period']}: {actual:.0f} units")

        result_df = pd.DataFrame({
            "Method": ["Moving Average", "Exponential Smoothing", "ARIMA", "Your selected forecast"],
            "Forecast": [rec["ma"], rec["es"], rec["arima"], rec["selected_forecast"]],
        })
        result_df["Actual"] = actual
        result_df["Absolute Error"] = (result_df["Actual"] - result_df["Forecast"]).abs()
        result_df["Business Cost"] = result_df["Forecast"].apply(lambda f: business_cost(f, actual, under_cost, over_cost))
        st.dataframe(
            result_df.style.format({"Forecast": "{:.1f}", "Actual": "{:.0f}", "Absolute Error": "{:.1f}", "Business Cost": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Business-cost illustration: ${under_cost:,.2f} per unit underforecast and ${over_cost:,.2f} per unit overforecast."
        )

        st.markdown("### Decide what to do next")
        next_action = st.radio(
            "Based on the new actual demand, what will you do for the next period?",
            ["Keep the same approach", "Change a model parameter", "Change forecasting method", "Need more evidence before changing"],
            key=f"action_{round_idx}",
        )
        reflection = st.text_area(
            "What did this period teach you about the forecasting methods?",
            key=f"reflection_{round_idx}",
            max_chars=800,
        )
        if st.button("Save Decision and Continue", type="primary", disabled=len(reflection.strip()) < 10):
            st.session_state.records[-1]["next_action"] = next_action
            st.session_state.records[-1]["reflection"] = reflection.strip()
            st.session_state.current_round += 1
            st.session_state.locked = False
            st.rerun()

else:
    st.success("Forecasting rounds complete.")
    df = pd.DataFrame(records)
    st.markdown("## Final Performance Summary")

    rows = []
    for label, col in [("Moving Average", "ma"), ("Exponential Smoothing", "es"), ("ARIMA", "arima")]:
        mad = (df[col] - df["actual"]).abs().mean()
        cost = sum(business_cost(f, a, under_cost, over_cost) for f, a in zip(df[col], df["actual"]))
        rows.append({"Approach": label, "MAD": mad, "Business Cost": cost})
    selected_mad = (df["selected_forecast"] - df["actual"]).abs().mean()
    selected_cost = sum(business_cost(f, a, under_cost, over_cost) for f, a in zip(df["selected_forecast"], df["actual"]))
    rows.append({"Approach": "Student-selected forecasts", "MAD": selected_mad, "Business Cost": selected_cost})
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df.style.format({"MAD": "{:.2f}", "Business Cost": "${:,.2f}"}), use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="warning"><b>Interpretation:</b> The method with the lowest statistical error is not automatically the best operational decision. '
        'Compare the pattern of errors, responsiveness after demand changes, and the business consequences of over- and underforecasting.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Round-by-round record")
    round_view = df[["round", "period", "actual", "ma", "es", "arima", "selected_method", "selected_forecast"]].copy()
    round_view.columns = ["Round", "Period", "Actual", "Moving Average", "Exponential Smoothing", "ARIMA", "Selected Method", "Selected Forecast"]
    st.dataframe(round_view, use_container_width=True, hide_index=True)

    pdf_bytes, verification_code, generated = make_report(
        st.session_state.student_name,
        st.session_state.student_id,
        records,
        under_cost,
        over_cost,
    )
    st.markdown("### Submit your lab record")
    st.write(f"Verification code: **{verification_code}**")
    st.caption(f"Report generated: {generated.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    st.download_button(
        "Download Verified Forecasting Lab Report (PDF)",
        data=pdf_bytes,
        file_name=f"Forecasting_Lab_{st.session_state.student_id}.pdf",
        mime="application/pdf",
        type="primary",
    )
