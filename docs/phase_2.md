# PHASE 2 — Feature Pipeline & Feature Store

> Prerequisite: Phase 1 complete (`data_fetcher.py` works, Hopsworks connection verified, `config/cities.yaml` exists). See `brain.md` §4 for the full feature spec.

## Objectives
1. Turn a raw fetched row into a full feature row (time-based + city + lag + rolling + derived features), computed correctly **per city**.
2. Create a Hopsworks Feature Group with the right schema.
3. `feature_pipeline.py` runs end-to-end for **every city in `config/cities.yaml`** on each run: fetch → engineer → push to Feature Store.

## Tasks
1. Write `src/feature_engineering.py`:
   - `add_time_features(df)` → hour, day_of_week, day_of_month, month, is_weekend
   - `add_city_encoding(df)` → one-hot or label-encoded `city` column
   - `add_lag_features(df)` → AQI at t-1h, t-3h, t-6h, t-24h, computed **grouped by city** (requires querying previously stored rows from the Feature Store filtered to that city, not just the current fetch, and never pulling a previous row from a different city)
   - `add_rolling_features(df)` → rolling mean/std of AQI over 6h and 24h windows, grouped by city
   - `add_derived_features(df)` → AQI change rate, grouped by city
2. Write `src/feature_pipeline.py`:
   - Loads the city list via `load_cities_config()` from Phase 1.
   - For each city: calls `fetch_combined_data(city, lat, lon)`, pulls that city's recent history from the Feature Store (needed to compute lag/rolling features), calls the engineering functions above, and inserts the row.
   - Defines/gets the Hopsworks Feature Group (`aqi_features`, primary key = `city` + `timestamp`, event_time = `timestamp`) once, shared across all cities.
   - Wraps each city's fetch+insert in its own try/except so one city's failure doesn't stop the others from being processed in the same run.
3. Handle the "cold start" problem per city: for the very first few runs of a given city, lag/rolling features won't have enough history — decide and document a fallback (e.g., fill with current value, or skip lag features until enough history exists for that specific city).
4. Add basic logging (print statements or `logging` module), including which city is currently being processed, so CI/CD logs are readable later.

## Testing / Definition of Done
- [ ] Running `python src/feature_pipeline.py` manually completes with no errors and prints a confirmation of what was inserted **for each city**.
- [ ] Hopsworks UI shows the `aqi_features` Feature Group with the correct schema (all time-based, city, lag, rolling, derived columns present) and rows for every configured city.
- [ ] Run the script 3+ times across a real time gap (e.g., every 15–30 min over an hour) and confirm, per city: (a) no duplicate rows for the same city+timestamp, (b) lag/rolling values update sensibly between runs.
- [ ] Spot-check one row's `aqi_change_rate` by hand for at least two different cities: does `(AQI_t - AQI_t-1)/AQI_t-1` match what's stored, and is it computed from that same city's previous row (not another city's)?
- [ ] Temporarily force one city to fail (e.g., bad coordinates) and confirm the other cities still get processed and inserted correctly in the same run.
- [ ] No secrets are printed in logs.

**Do not proceed to Phase 3 until every box above is checked.**