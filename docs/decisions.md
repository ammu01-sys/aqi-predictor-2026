# Technical Decisions & Debugging Findings

This document outlines key technical design choices, debugging discoveries, and system limitations encountered during Phase 1 (Data & Architecture Setup) and Phase 2 (Feature Pipeline & Engineering).

---

## 1. Cold-Start Fallback Strategy

When initializing the system or processing new cities without sufficient historical records in the Hopsworks Feature Store, lag and rolling metrics cannot be calculated directly from past hours. To prevent pipeline failure, a persistence-fill strategy was adopted as a deliberate design choice: lag and rolling-mean features are populated using the city's current AQI value, while rolling standard deviations and AQI change rates default to `0.0`. This choice allows the feature pipeline to execute deterministically from cold-start while building up history, and is explicitly documented in the `feature_engineering.py` codebase.

---

## 2. City Encoding Strategy

Rather than using integer label encoding (e.g., mapping cities to 0 through 7), dynamic one-hot encoding was selected for city categorical representation (e.g., `city_lahore`, `city_karachi`). This decision was driven by the downstream requirement to evaluate Ridge Regression alongside tree-based models. Ridge Regression interprets integer labels as continuous ordinal values, which would incorrectly impose a artificial mathematical ranking on geographical locations; one-hot encoding avoids this bias completely.

---

## 3. Timezone Bug Discovery & Resolution

AQICN's API returns observation timestamps in the monitoring station's local timezone (e.g., UTC+5 for Pakistani cities) rather than UTC. The initial implementation incorrectly assumed these timestamps were UTC and applied `.replace(tzinfo=timezone.utc)`, which mislabeled local times as UTC without shifting the hour, storing timestamps ~5 hours ahead of true UTC. The bug was resolved in `data_fetcher.py` and `utils.py` by parsing the station's explicit ISO offset (`time.iso`) and converting it to true UTC using `.astimezone(timezone.utc)` and `pd.to_datetime(..., utc=True)`. Verification confirmed that a 06:00 AM PKT station observation now correctly parses to 01:00 AM UTC.

---

## 4. Hopsworks Materialization Job Reliability (Known Limitation)

During feature pipeline execution, the Hopsworks free-tier Spark materialization job (`aqi_features_1_offline_fg_materialization`) frequently reports a `FAILED` status even when data is successfully committed to Hudi storage. Log inspection revealed this false signal is caused by a `SocketTimeoutException` in Spark's Prometheus metrics-pushgateway reporter after the Hudi DeltaStreamer commit finishes. To distinguish false alarms from true materialization failures, pipeline verification logic verifies actual Feature Group row count growth rather than relying solely on job status reporting. A rarer genuine failure mode was also observed during rapid consecutive runs, establishing that isolated hourly execution schedules perform reliably.

---

## 5. Hopsworks Project Migration

Initial feature pipeline testing on the original Hopsworks project (`aqi_preditcor`) encountered persistent materialization failures across all job runs spanning three weeks, even prior to running custom code. This pointed to a stale or corrupted Spark cluster resource attached to that specific project namespace. Migrating to a fresh project (`aqiii_preditcor`) immediately resolved the materialization locks for both initial Feature Group creation and subsequent upsert runs, as confirmed by consistent row count growth (0 → 8 → 16 rows).

---

## 6. Missing Dependencies Discovered During Testing

End-to-end pipeline and feature store testing uncovered two required runtime dependencies missing from the initial environment specification: `confluent-kafka` and `pyjks`. Both have been added to `requirements.txt`. Crucially, `pyjks` includes a `twofish` C-extension dependency that fails to build on Windows environments lacking C++ Build Tools; because `twofish` is not required for Hopsworks certificate handling, `pyjks` is installed via `pip install pyjks --no-deps` followed by pure-Python support packages (`javaobj-py3`, `pyasn1`, `pyasn1-modules`, `pycryptodomex`). This setup procedure is documented in both `requirements.txt` and `README.md`.

---

## 7. Phase 3 Historical Backfill API Access & Single-API Fallback

Empirical verification of API historical capabilities confirmed that OpenWeather's Air Pollution History API (`/data/2.5/air_pollution/history`) provides 90+ days of complete, hourly historical pollutant observations (PM2.5, PM10, O3, NO2, SO2, CO) for all 8 Pakistani cities. However, OpenWeather's Historical Weather API (`/3.0/onecall/timemachine`) returned HTTP 401 Unauthorized because historical weather data requires a separate paid plan. In accordance with `brain.md §3`'s single-API fallback directive, the historical backfill (`src/backfill.py`) populates 60–90 days of hourly air quality features and target values (`target_24h`, `target_48h`, `target_72h`), setting missing historical weather variables to `null` with `weather_source_ok = False` and `aqi_source_ok = True`. This ensures a robust multi-city training dataset (~16,000+ hourly rows) without blocking pipeline execution.

---

## 8. Consistent End-to-End AQI Source: OpenWeather EPA Formula

Early versions of the pipeline used AQICN's proprietary station AQI value as the primary `aqi` field in live ingestion, while the historical backfill derived AQI from OpenWeather's historical pollutant concentrations using the US EPA piecewise linear formula (`compute_aqi_from_pollutants()`). Empirical cross-validation revealed a 46.7% average divergence between these two sources (e.g., Lahore: 91 vs 115, Islamabad: 91 vs 164), caused by the fundamental difference between physical micro-sensor ground measurements (AQICN station) and satellite/chemical-transport grid-cell modelling (OpenWeather). Attempting to resolve this via per-city single-point scaling ratios produced negative R² on the 48h and 72h horizons, confirming the calibration was statistically unsound.

The adopted design uses **one single AQI definition end-to-end**: `compute_aqi_from_pollutants()` applied to **OpenWeather's pollutant concentrations** (µg/m³), for both historical backfill (`src/backfill.py`, `/data/2.5/air_pollution/history`) and live hourly ingestion (`src/data_fetcher.py`, `/data/2.5/air_pollution`). Both endpoints return the same pollutant species in identical concentration units, making historical and live AQI values directly comparable without any cross-source reconciliation or scaling. AQICN's native station AQI is preserved as a secondary field (`aqicn_reference_aqi`) for display and monitoring purposes only — it is not used as a model feature or training target.

---

## 9. Hyperparameter Tuning Scope for Phase 4

For the Phase 4 modeling evaluation, hyperparameter tuning scope was deliberately focused: Ridge Regression was tuned systematically across regularization strengths ($\alpha$) using `RidgeCV`, while Random Forest, XGBoost, and the Multi-Layer Perceptron (MLP) were executed with robust, lightly-set baseline hyperparameters (e.g., standard tree depth and estimators) to establish fair, leak-free model comparison across all 3 horizons. Full Bayesian and extensive grid search tuning is deferred to subsequent project phases.

---

## 10. Weather-Null Training/Serving Mismatch & Inference Safeguards

Because historical weather data was unavailable from the free-tier API, the Phase 4 model versions are trained strictly on pollutant concentrations, lag metrics, rolling statistics, temporal cycles, and one-hot city indicators, with all weather features (`temperature`, `humidity`, `wind_speed`, `pressure`) excluded. Consequently, live weather features generated by `feature_pipeline.py` must NOT be passed to these model versions during inference until a weather-inclusive dataset and retrained model exist. Model serving pipelines enforce an explicit schema assertion rejecting any input feature vector containing weather attributes for this model artifact version.

---

## 11. `aqicn_reference_aqi` — Display-Only Reference Field

Because the primary `aqi` field is now uniformly computed from OpenWeather's pollutant concentrations via the EPA formula (see Section 8), AQICN's native station AQI is stored as a separate field `aqicn_reference_aqi` with the following properties:

- **Source**: AQICN's real-time station API (`fetch_aqicn_data()`), populated only during live hourly ingestion. Set to `null` for all historical backfill rows (unavailable from OpenWeather's historical endpoint).
- **Purpose**: Dashboard display and manual monitoring — allows users to compare the model's internally-consistent EPA-formula AQI against the publicly visible AQICN reading for the same city and hour.
- **Modeling exclusion**: `aqicn_reference_aqi` is explicitly excluded from all model feature sets and is never used as a training target. The `AQIPredictorModelWrapper` does not accept it as an input and no feature engineering is applied to it.
- **Schema**: Typed as a nullable `float64` column in `cast_dataframe_schema()`. Its presence as `null` in historical rows does not affect any training, validation, or test split logic.

---

## 12. Phase 4 Model Selection Outcome: Persistence as Documented Baseline

After evaluating Ridge Regression, XGBoost (one-hot and integer encoding), Random Forest (one-hot and integer), and MLP Neural Network alongside the Persistence Baseline across all three forecast horizons, **Persistence Baseline is the Phase 4 winner on all three horizons**. No ML model artifact was registered in the Hopsworks Model Registry, as no model meaningfully improved over persistence on the held-out chronological test set.

### Final Test-Set Results (Consistent AQI Dataset)

| Horizon | Persistence RMSE | Persistence R² | Best ML Model | Best ML RMSE | Best ML R² |
|---|---|---|---|---|---|
| 24h | 21.58 | 0.596 | Ridge (one-hot) | 22.07 | 0.577 |
| 48h | 27.79 | 0.351 | XGBoost (one-hot) | 30.50 | 0.218 |
| 72h | 27.51 | 0.376 | XGBoost (one-hot) | 32.32 | 0.138 |

A time-boxed `RandomizedSearchCV` (20 iterations, 3-fold `TimeSeriesSplit`) was applied to XGBoost on the 48h and 72h horizons as a diagnostic. Tuning improved default XGBoost R² from 0.2034 → 0.3349 (48h) and 0.1588 → 0.3357 (72h), but both remained below Persistence (0.3511 and 0.3759 respectively), trailing by 0.34 and 0.87 RMSE points.

### Root Causes

1. **Smoothed satellite-modelled pollutant series**: OpenWeather's Air Pollution API derives pollutant concentrations from chemical transport models (CAMS/satellite), which apply spatial and temporal smoothing. The resulting AQI series has lower short-term variability than ground station readings, weakening the signal that lag and rolling features can exploit to outperform persistence.

2. **Absent weather features**: Temperature, humidity, and wind speed are the primary physical drivers of AQI change vs. persistence (diurnal convection, nocturnal inversion, wind dilution). With `weather_source_ok = False` for all historical rows, these predictors are unavailable in this training version. Their absence is the single most likely cause of ML underperformance at 48h and 72h horizons.

### Per-City vs. Overall R² Paradox

The overall R² for Persistence is positive (0.376 on 72h) while **all per-city R² values are negative** (ranging from −0.893 to −2.251). This is a cross-city variance effect: when pooled across 8 cities with different AQI baselines, predicting "current AQI" captures between-city variance against a global test-set mean, inflating overall R². Within each individual city's temporal sequence, persistence performs worse than that city's own mean — confirming that meaningful temporal structure exists to be learned, but requires weather features or a longer training window to unlock.

### Path Forward (Phase 5+)

- Weather feature incorporation (paid OpenWeather plan or an alternative free source) is the highest-priority improvement for Phase 5 model iteration.
- Persistence Baseline is documented as the valid Phase 4 production baseline and will be used as the inference fallback until a weather-inclusive model demonstrably beats it.
