# PHASE 3 — Historical Backfill & EDA

> Prerequisite: Phase 2 complete (feature pipeline works and pushes valid rows to Hopsworks). See `brain.md` §4–5.

## Objectives
1. Build a real training dataset by backfilling historical (features, targets) data.
2. Understand the data through EDA before training anything.
3. Finalize target column definition (t+24h, t+48h, t+72h AQI).

## Tasks
1. Write `src/backfill.py`:
   - Loads the city list via `load_cities_config()`.
   - For **each city**, uses the historical endpoint of AQICN/OpenWeather to fetch data for a date range (aim for 60–90 days if the API allows; if history is limited, backfill as far back as possible and document the limitation).
   - Loops over each historical timestamp per city, engineers features the same way as `feature_pipeline.py` (reuse `feature_engineering.py` — do not duplicate logic), always grouping lag/rolling computation by city.
   - Computes **targets**: for each row at time t (for a given city), target_24h = AQI at t+24h **for that same city**, target_48h = AQI at t+48h, target_72h = AQI at t+72h (looked up from that city's own historical series — never cross-city).
   - Pushes rows (features + targets) into the Feature Store — either the same Feature Group with nullable target columns, or a separate `aqi_targets` Feature Group joined on `city`+`timestamp` (decide and document which).
   - Wraps each city's backfill loop in try/except so one city's API/history issue doesn't abort backfill for the rest.
2. Pull the full backfilled multi-city dataset into a notebook (`notebooks/eda.ipynb`).
3. Perform EDA (both **pooled across all cities** and **per city** where noted):
   - AQI time series plot per city (trend + any obvious seasonality: daily/weekly cycles) — overlay or facet by city
   - Distribution of AQI (histogram), overall and per city — is it skewed? Any extreme outliers? Do cities differ meaningfully in typical AQI range?
   - Correlation heatmap: pollutants/weather vs AQI (pooled)
   - Missing data report (% missing per column, and where gaps occur), broken down by city in case one city's API coverage is worse than others
   - Autocorrelation plot of AQI per city (justifies lag features, and checks whether autocorrelation structure is similar or different across cities)
4. Based on EDA findings, revisit `feature_engineering.py` if something important surfaces (e.g., a weather variable turns out highly predictive and should get its own lag features, or one city behaves very differently from the rest).

## Testing / Definition of Done
- [ ] `python src/backfill.py` completes without errors and reports how many rows were inserted **per city**.
- [ ] Hopsworks Feature Store shows a dataset with enough rows to train on for **every** configured city (minimum few hundred rows per city recommended; more is better).
- [ ] Spot-check 2–3 random rows across at least two different cities: does `target_24h` actually equal the real AQI value 24 hours after that row's timestamp, for that same city? Verify manually against raw source.
- [ ] Confirm no row's target was accidentally computed using another city's data (e.g., check a row for City A doesn't have a target value that matches City B's series).
- [ ] EDA notebook runs top-to-bottom with no errors and produces all listed plots, with city clearly distinguishable in each relevant plot.
- [ ] No column in the final dataset has more than a reasonable % of missing values (define your own threshold, e.g., <10%) for any individual city without a documented reason.

**Do not proceed to Phase 4 until every box above is checked.**