# BRAIN.md — Pearls AQI Predictor (Master Project Reference)

> This file is the single source of truth for the project. Read this in full before touching any phase file. Every phase file (`phase1_...md` through `phase6_...md`) assumes the context in this document.

---

## 1. Project Summary

**Name:** Pearls AQI Predictor
**Goal:** Predict the Air Quality Index (AQI) for a **fixed set of supported cities** (5–10, configurable) for the **next 3 days**, using a **100% serverless stack** (no self-managed servers/databases — everything runs on managed free-tier services + scheduled jobs). The dashboard lets the user **select any city from this supported list** and see its live data + 3-day forecast.

**Core idea:** Build 4 decoupled pieces glued together by a **Feature Store** and a **Model Registry**, instead of one monolithic script:

```
[External Weather/AQI API]
        |
        v
[Feature Pipeline]  ---(runs hourly via CI/CD)---> [Feature Store]
                                                          |
                                                          v
                                              [Training Pipeline] --(runs daily via CI/CD)--> [Model Registry]
                                                          |                                          |
                                                          v                                          v
                                                  [Feature Store]  <----------  [Web App / Dashboard] reads both
```

The Feature Store and Model Registry decouple the pipelines: the feature pipeline doesn't need to know about the model, the training pipeline doesn't need to know about the API, and the web app doesn't need to know about either — it just reads the latest features + the best registered model.

---

## 2. Official Technology Stack

| Layer | Tool(s) | Notes |
|---|---|---|
| Language | Python 3.10+ | All scripts |
| Data source | AQICN API or OpenWeather Air Pollution API | Pick ONE as primary; document the choice |
| Feature Store / Model Registry | **Hopsworks** (recommended, generous free tier, purpose-built) or Vertex AI | Use Hopsworks unless there's a strong reason not to |
| ML libraries | Scikit-learn (Ridge Regression, Random Forest), TensorFlow or PyTorch (for deep learning models) | Must compare statistical + tree + deep learning |
| Orchestration / CI-CD | GitHub Actions (recommended for simplicity) or Apache Airflow | Cron-based scheduled runs |
| Web app | Streamlit or Gradio (frontend) + Flask or FastAPI (backend, optional if Streamlit calls Hopsworks directly) | Streamlit alone is sufficient for MVP |
| Explainability | SHAP (preferred) or LIME | Feature importance on best model |
| Version control | Git + GitHub | Repo holds all code + workflows |

---

## 3. Data & API Details

- **Supported cities:** a **fixed list of 5–10 cities**, defined in a single config file (`config/cities.yaml` or `config/cities.json`), each entry holding `city_name`, `lat`, `lon`. All pipelines loop over this list — nothing is hardcoded to one city. Adding a city later = adding one entry to this config file.
  - **Finalized list for this project (Pakistan):** Lahore, Karachi, Islamabad, Faisalabad, Multan, Peshawar, Rawalpindi, Gujranwala — 8 cities chosen for a mix of consistently high pollution levels (Lahore, Faisalabad, Gujranwala are frequently among the world's most polluted cities) and geographic/population spread across the country. See `config/cities.yaml` for exact coordinates.
- **Approach: DUAL API** — use both AQICN and OpenWeather, each for what they're best at, for **every city in the config list**:
  - **AQICN API** (`https://aqicn.org/api/`) → source of truth for **AQI + pollutant breakdown** (PM2.5, PM10, O3, NO2, SO2, CO). Free token. Has a historical/feed endpoint useful for backfill.
  - **OpenWeather API** (Current Weather / One Call) → source of truth for **weather fields**: temperature, humidity, wind speed, pressure. Free tier. Has a historical endpoint for backfill.
  - `data_fetcher.py` implements **two functions**: `fetch_aqicn_data(city, lat, lon)` and `fetch_openweather_data(lat, lon)`. A third function `fetch_combined_data(city, lat, lon)` calls both and merges them into a single clean dict, keyed on a common rounded-to-the-hour timestamp. This function is called once per city per pipeline run.
- **Timestamp alignment:** Both APIs return slightly different timestamps. Round each to the nearest hour (`timestamp.replace(minute=0, second=0, microsecond=0)`) before merging so the two sources line up on the same row.
- **Fallback/error handling:** If one API fails for a given city on a given run, don't discard that city's row — insert what you have and fill the missing source's fields with `null`/`NaN`, flagged by a boolean column (e.g., `weather_source_ok`, `aqi_source_ok`). One city's API failure must never block the other cities in the same run — each city's fetch+insert should be wrapped so an exception is caught, logged, and the loop continues.
- **Single-API fallback option:** If dual-API integration proves too complex to debug initially, it's acceptable to start with AQICN alone (it returns some weather fields too, just less reliably) and add OpenWeather once the pipeline is stable. Document whichever path you actually took in the final report.
- **Rate limits:** Free tiers are limited (AQICN: ~1000 calls/day per token; OpenWeather: ~60 calls/min on free tier for pollution API, check current limits). With ~5–10 cities × 2 API calls each × hourly runs, usage stays well within free-tier limits — confirm the math for your exact city count before finalizing.

---

## 4. Feature Engineering Spec

### Raw fields to fetch per timestamp per city:
- PM2.5, PM10, O3, NO2, SO2, CO (pollutant concentrations)
- Temperature, Humidity, Wind speed, Pressure
- AQI (if provided directly, else computed)
- Timestamp (UTC), City

### Multi-city handling:
- The feature pipeline loops over **every city in `config/cities.yaml`** on each run, computing and inserting one feature row per city.
- `city` is a **categorical feature** the models must use — either one-hot encoded or label/target-encoded — so a single set of models can learn city-specific baseline differences (e.g., one city's typical AQI range vs a cleaner city) rather than training a fully separate model per city. This keeps the modeling pipeline simple while still supporting multiple cities well.
- Lag/rolling features (below) must be computed **per city independently** — a lag feature must never pull the previous row from a *different* city. Always filter/group by `city` before computing lags/rolling stats.

### Engineered features:
- **Time-based:** hour of day, day of week, day of month, month, is_weekend (0/1)
- **City:** one-hot or label-encoded `city` column
- **Lag features (per city):** AQI at t-1h, t-3h, t-6h, t-24h
- **Rolling stats (per city):** rolling mean & std of AQI over last 6h and 24h windows
- **Derived:** AQI change rate = (AQI_t - AQI_t-1) / AQI_t-1 (or simple delta), computed per city
- **Weather interactions (optional/advanced):** temperature-humidity index, wind speed bucket

### Targets:
Predicting AQI at **t+24h, t+48h, t+72h** (3 separate horizons), per city. Two valid approaches — pick one and document it:
1. **Three separate models/target columns**, one per horizon, trained on the pooled multi-city dataset with `city` as a feature (simpler, recommended first).
2. **One multi-output/sequence model** (e.g., LSTM outputting a 3-length vector) — advanced/stretch goal.

### Primary key for Feature Store schema:
`city` + `timestamp` (composite primary key in the Feature Group) — this is what makes multi-city support natural: every row is uniquely identified by which city it belongs to.

---

## 5. Modeling Spec

### Baseline (mandatory, must always be reported):
- **Persistence model**: prediction for t+24h/48h/72h = AQI right now, computed per city. This proves whether the ML models actually add value.

### Multi-city modeling approach (adopted):
- Train **one pooled model per horizon** (not one model per city) on the combined dataset across all configured cities, using the encoded `city` column as a feature. This is more data-efficient than training separate models per city, especially early on when each city has limited history.
- Evaluate performance **per city** as well as overall — a pooled model could do well on average while performing poorly on one specific city, and that must be caught and reported.

### Models to try (mandatory set):
- Ridge Regression (scikit-learn) — statistical baseline
- Random Forest Regressor (scikit-learn) — tree-based
- Gradient Boosting (XGBoost/LightGBM) — strongly recommended addition, usually best for tabular time-series
- LSTM or simple feed-forward NN (TensorFlow or PyTorch) — deep learning entry, stretch goal but expected per guidelines ("from statistical to deep learning")

### Evaluation:
- Metrics: **RMSE, MAE, R²** for each model, for each horizon (24h/48h/72h)
- **Chronological train/test split** — never randomly shuffle time series data. E.g., train on first 80% of dates, test on last 20%.
- Keep a comparison table of all models × all horizons × all metrics — this goes directly into the final report.

### Explainability:
- Run **SHAP** on the best-performing model to identify which features drive AQI predictions the most. Include SHAP summary plots in the report and optionally in the dashboard.

### Model Registry:
- Push the winning model (per horizon, or one combined) to Hopsworks Model Registry with metadata: metrics, training date, feature list, model version.

---

## 6. Automation / CI-CD Spec

| Job | Frequency | Cron expression (UTC) | Script |
|---|---|---|---|
| Feature Pipeline | Every hour | `0 * * * *` | `feature_pipeline.py` |
| Training Pipeline | Every day | `0 0 * * *` | `training_pipeline.py` |

- Implemented via **GitHub Actions** workflows in `.github/workflows/`.
- Secrets required: `AQICN_API_KEY`, `OPENWEATHER_API_KEY`, `HOPSWORKS_API_KEY`, `HOPSWORKS_PROJECT_NAME` — stored as GitHub repo secrets, never committed to code. `config/cities.yaml` (the list of supported cities) is a **committed file**, not a secret, since it contains no sensitive data.
- Each workflow: checkout repo → setup Python → install requirements → run script (which internally loops over all cities in `config/cities.yaml`) → (optional) notify on failure.

---

## 7. Web App / Dashboard Spec

**Stack:** Streamlit (fastest to build + free deploy on Streamlit Community Cloud).

**Must show:**
1. **City dropdown selector** at the top of the dashboard, populated from `config/cities.yaml` (the same fixed list the pipelines track) — this is now a **mandatory** element, not optional, since the whole point is letting the user pick which of the supported cities to view.
2. Current AQI reading + category (Good / Moderate / Unhealthy for Sensitive Groups / Unhealthy / Very Unhealthy / Hazardous) for the **selected city**, color-coded.
3. 3-day forecast (line/bar chart) for the selected city, with confidence framing.
4. Historical AQI trend chart (last 7/30 days from Feature Store) for the selected city.
5. Feature importance chart (SHAP values) for transparency — can be shown once for the pooled model, noting it applies across all cities.
6. **Alert banner** that visually triggers when the selected city's predicted AQI crosses a hazardous threshold (e.g., >150 or >200 depending on scale used).

**App logic flow:**
1. Connect to Hopsworks (Feature Store + Model Registry) using API key.
2. Render the city dropdown; read the user's selection.
3. Pull latest feature row(s) for the **selected city only** (filter Feature Store query by `city == selected_city`).
4. Load the pooled registered model for each horizon (same model serves all cities; the `city` feature value changes based on selection).
5. Compute predictions for t+24h/48h/72h using the selected city's row.
6. Render all dashboard elements for that city; re-run steps 3–6 whenever the dropdown selection changes.

**Deployment:** Streamlit Community Cloud (free), linked to GitHub repo, auto-redeploys on push.

---

## 8. Guidelines Checklist (from original brief — do not skip)

- [ ] Perform EDA to identify trends (seasonality, correlations, missing data, outliers)
- [ ] Use a variety of forecasting models — statistical → tree-based → deep learning
- [ ] Use SHAP or LIME for feature importance explanations
- [ ] Add alerts for hazardous AQI levels
- [ ] Feature pipeline automated hourly
- [ ] Training pipeline automated daily
- [ ] Fully serverless (no self-hosted DB/server — Hopsworks/Vertex AI + GitHub Actions + Streamlit Cloud only)

---

## 9. Final Deliverables (what "done" looks like)

1. **End-to-end AQI prediction system** — all 4 components working together.
2. **Scalable, automated pipeline** — CI/CD running feature pipeline hourly, training pipeline daily, with logs proving it's actually running unattended.
3. **Interactive dashboard** — live, deployed, showing real-time + forecasted AQI.
4. **Detailed report** — EDA findings, architecture diagram, feature list, model comparison table, chosen model + why, SHAP insights, screenshots, CI/CD proof, limitations & future work.

---

## 10. Suggested Repository Structure

```
pearls-aqi-predictor/
├── .github/
│   └── workflows/
│       ├── feature_pipeline.yml
│       └── training_pipeline.yml
├── config/
│   └── cities.yaml              # fixed list of supported cities: name, lat, lon
├── src/
│   ├── data_fetcher.py          # calls AQICN/OpenWeather API
│   ├── feature_engineering.py   # transforms raw -> features (per-city aware)
│   ├── feature_pipeline.py      # loops over cities: fetch + engineer + push to Feature Store
│   ├── backfill.py              # loops feature logic over historical dates x cities
│   ├── training_pipeline.py     # pulls pooled multi-city data, trains, evaluates, pushes to Model Registry
│   └── utils.py                 # shared helpers, AQI calculation formula, config loader
├── notebooks/
│   └── eda.ipynb
├── app/
│   └── streamlit_app.py         # includes city dropdown selector
├── tests/
│   └── test_pipeline.py
├── docs/
│   ├── brain.md
│   ├── phase1_...md ... phase6_...md
│   └── report.md (final deliverable, written at the end)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 11. Phase Breakdown (high level — see individual phase files for detail)

| Phase | Title | Core Outcome |
|---|---|---|
| 1 | Setup & Data Access | Accounts, repo, API keys, raw data fetcher working |
| 2 | Feature Pipeline & Feature Store | Feature engineering script pushes clean feature rows to Hopsworks |
| 3 | Historical Backfill & EDA | Training dataset built; trends/patterns understood |
| 4 | Training Pipeline & Model Registry | Multiple models trained, evaluated, best one registered |
| 5 | CI/CD Automation | Hourly + daily pipelines running unattended on GitHub Actions |
| 6 | Web App, Explainability & Report | Live dashboard + SHAP + alerts + final report |

Work through these phases **in order**. Do not start Phase 4 without completing Phase 3 (no data = nothing to train on). Do not start Phase 5 until Phases 2 & 4 scripts run correctly manually at least once.