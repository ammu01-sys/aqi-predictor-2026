# PHASE 6 — Web App, Explainability, Alerts & Final Report

> Prerequisite: Phase 5 complete (pipelines running automatically, real data + registered models exist). See `brain.md` §7–9.

## Objectives
1. Build and deploy a live Streamlit dashboard.
2. Show real-time AQI, 3-day forecast, historical trend, SHAP feature importance, and hazard alerts.
3. Write the final project report.

## Tasks
1. Write `app/streamlit_app.py`:
   - Connects to Hopsworks using API key (from Streamlit secrets, not hardcoded).
   - Loads the city list via `load_cities_config()` and renders a **dropdown selector** at the top of the page — this is the primary navigation control for the whole dashboard.
   - On selection, pulls the latest feature row(s) for the **selected city only** from the Feature Store (filter by `city == selected_city`).
   - Loads the pooled registered model(s) per horizon from the Model Registry (same model object serves every city; only the input row's `city` feature changes).
   - Computes predictions for t+24h, t+48h, t+72h for the selected city.
   - Renders (all scoped to the currently selected city):
     - Current AQI + color-coded category card
     - 3-day forecast chart
     - Historical trend chart (last 7/30 days, pulled from Feature Store, filtered to selected city)
     - SHAP feature importance chart (can be precomputed in Phase 4 and loaded, or computed live) — noted as applying to the pooled model across all cities
     - Alert banner if any predicted horizon crosses a hazardous threshold (define thresholds per standard AQI categories, e.g., >150 = Unhealthy, >200 = Very Unhealthy, >300 = Hazardous)
   - Re-runs the pull/predict/render logic whenever the dropdown selection changes (Streamlit's natural rerun-on-widget-change behavior handles this if state is read from the selector each run).
2. Add a `requirements.txt` specific to the app (or reuse the main one) for Streamlit Cloud deployment.
3. Add `.streamlit/secrets.toml.example` documenting required secrets for deployment (real one goes only in Streamlit Cloud's secrets manager, not the repo).
4. Deploy to Streamlit Community Cloud, linked to the GitHub repo.
5. Write `docs/report.md` (or a Word/PDF version) covering:
   - Project overview & architecture diagram
   - Data source & API choice justification
   - Multi-city design decision (fixed list, pooled model with city as a feature) & justification
   - Feature engineering summary
   - EDA findings (from Phase 3, in your own words, including any per-city differences found)
   - Model comparison table (from Phase 4, overall + per-city breakdown) + chosen model + justification
   - SHAP insights
   - CI/CD setup & proof of automated runs (screenshots of Actions history)
   - Dashboard screenshots (showing the city dropdown in action, ideally with 2+ different cities selected)
   - Limitations & future work (e.g., fixed city list vs fully dynamic city search, limited historical data, API rate limits)

## Testing / Definition of Done
- [ ] `streamlit run app/streamlit_app.py` works locally with no errors, showing all required elements including the city dropdown.
- [ ] Selecting each city in the dropdown, one at a time, correctly updates every element on the dashboard (AQI value, forecast, trend chart, alert banner) — no stale data left over from the previously selected city.
- [ ] Deployed Streamlit Cloud URL is publicly accessible and loads correctly (test in an incognito window / different device).
- [ ] Force a hazardous AQI test case (e.g., temporarily mock a high prediction value) for one city and confirm the alert banner actually triggers visually for that city, while a different, non-hazardous city does NOT show the alert.
- [ ] Confirm the dashboard reflects a genuinely fresh Feature Store row (compare its "last updated" timestamp against the latest hourly pipeline run) for the selected city.
- [ ] `docs/report.md` contains every section listed above, with real numbers/plots/screenshots — no placeholder text left in.
- [ ] Full walkthrough test: open the deployed app cold (no prior context), pick a city from the dropdown — can a stranger understand what they're looking at within 30 seconds? If not, revise labels/layout.

**Project is complete once every box in every phase file (1 through 6) is checked.**