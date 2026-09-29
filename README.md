# BAN 517 Forecasting Decision Lab — Version 5.0

## Public GitHub files
Upload these files/folders to the GitHub repository used by Streamlit Community Cloud:

- `app.py`
- `requirements.txt`
- `data/` (all assigned historical datasets)
- `README.md` (optional)

Do **not** upload:

- `INSTRUCTOR_SECRETS.toml`
- `INSTRUCTOR_ANSWER_KEY.csv`

The private files contain hidden future demand and grading answers.

## Streamlit Secrets
In Streamlit Community Cloud:

1. Open the deployed app.
2. Choose **Manage app → Settings → Secrets**.
3. Paste the complete contents of `INSTRUCTOR_SECRETS.toml`.
4. Replace `CHANGE-THIS-TO-A-PRIVATE-RANDOM-STRING` with a private random string.
5. Save.

## Student workflow

1. Enter name and student ID.
2. Download the assigned historical CSV.
3. Complete the forecasting calculations outside Streamlit.
4. Return to Streamlit and enter:
   - 3-period moving-average next-period forecast and MAD,
   - exponential-smoothing (alpha = 0.35) next-period forecast and MAD,
   - ARIMA (p,d,q), next-period forecast, and MAD,
   - recommended forecasting method.
5. Lock the answers.
6. View the hidden actual demand.
7. Complete the generated managerial calculation.
8. Download the verified PDF.

## Canvas submission
Students submit three files:

1. Verified Streamlit Forecasting Lab PDF
2. Excel forecasting workbook
3. PDF of completed Python/Colab notebook

## Automated score
The Streamlit report contains an automated score out of 65 points:

- Forecasting calculations and method selection: 45 points
- Post-reveal managerial calculation: 20 points

The remaining assignment points can be graded from the Excel workbook and Python notebook.

## Dataset assignment
Dataset assignment is deterministic from the student's entered ID. A student receives the same dataset when entering the same ID.

## Version 5.1 scoring

The automated Streamlit score is reported on a 10-point scale: 7 points for forecasting entries and 3 points for the post-reveal managerial calculation.
