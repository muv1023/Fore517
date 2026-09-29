# BAN 517 Forecasting Decision Lab

This Streamlit app creates a rolling forecasting exercise in which students must **lock a forecast before actual demand is revealed**.

## Public GitHub files

Upload these files/folders to the repository used by Streamlit Community Cloud:

- `app.py`
- `requirements.txt`
- `data/forecast_history.csv`

You may also upload this `README.md`.

**Do not upload the real future demand values to GitHub.**

## Streamlit Secrets

The hidden future demand values belong in Streamlit Community Cloud Secrets, not in the repository.

In Streamlit Community Cloud:

1. Open the deployed app.
2. Open **Settings / App settings**.
3. Find **Secrets**.
4. Paste the private TOML block supplied separately by the instructor setup file.
5. Save and reboot/redeploy the app if needed.

The app expects this structure:

```toml
[forecast_lab]
future_labels = ["2026-01", "2026-02"]
actuals = [120, 130]
underforecast_cost = 10.0
overforecast_cost = 3.0
```

## Student workflow

For each round students:

1. Inspect all demand known so far.
2. Calculate a 3-period moving-average forecast.
3. Calculate exponential smoothing with alpha = 0.35.
4. calculate an ARIMA forecast.
5. Select the forecast they would use operationally.
6. Explain their reasoning.
7. Lock the forecasts.
8. Reveal actual demand.
9. Observe absolute error and an illustrative business cost.
10. Decide whether to keep or change the forecasting approach.

After the final round, the app displays cumulative MAD and business cost and generates a verified PDF report.

## Important deployment note

The app stores each student's progress in Streamlit session state. A browser refresh or session expiration can reset progress. Students should complete the lab in one sitting.

## Changing the public history

Edit `data/forecast_history.csv`. Required columns are:

- `Period`
- `Demand`

Dates should be readable by pandas, preferably `YYYY-MM-DD`.

## Changing the hidden rounds

Change only the values in Streamlit Secrets. The number of `future_labels` must equal the number of `actuals`.
