# PHASE 4 — Training Pipeline & Model Registry

> Prerequisite: Phase 3 complete (backfilled dataset with features + targets exists in Feature Store, EDA done). See `brain.md` §5.

## Objectives
1. Train and fairly compare multiple models (statistical → tree-based → deep learning).
2. Evaluate with RMSE, MAE, R² using a chronological split.
3. Register the best model(s) to the Hopsworks Model Registry.

## Tasks
1. Write `src/training_pipeline.py`:
   - Pulls the full pooled multi-city (features, targets) dataset from the Feature Store via a Feature View, including the encoded `city` column as a feature (per `brain.md` §4–5).
   - Chronological train/test split **per city, then combined** (e.g., for each city take its first 80% of dates as train, last 20% as test, then union all cities' train rows and all cities' test rows — this avoids leaking one city's future into training while still pooling across cities). Do NOT randomly shuffle across the whole pooled set.
   - Trains a **persistence baseline** (current AQI = prediction for all horizons), computed per city, and aggregates its metrics — this is the number every other model must beat.
   - Trains: Ridge Regression, Random Forest, Gradient Boosting (XGBoost/LightGBM), and one deep learning model (LSTM or feed-forward NN in TensorFlow/PyTorch), for each of the 3 target horizons (24h/48h/72h), on the pooled dataset with `city` as a feature.
   - Computes RMSE, MAE, R² for every model × horizon combination **overall**, and additionally **broken down per city** — a pooled model doing well on average but badly on one city must be visible in the results, not hidden by the average.
   - Selects the best model per horizon (or overall, if using a multi-output model).
   - Runs SHAP on the best model to get feature importances (including how much the `city` feature itself matters); saves the SHAP summary plot.
   - Pushes the winning model(s) to Hopsworks Model Registry with metadata: metrics (overall + per city), feature list, training date, git commit hash if available.
2. Save the model comparison table (overall + per-city breakdown) to `docs/model_comparison.md` (or `.csv`) — this feeds directly into the final report.

## Testing / Definition of Done
- [ ] `python src/training_pipeline.py` runs end-to-end with no errors and prints/saves the comparison table.
- [ ] Every model has RMSE/MAE/R² computed for all 3 horizons, both overall and per city — no missing cells in the comparison table.
- [ ] At least one ML model beats the persistence baseline on at least 2 of 3 horizons overall (if not, investigate — this is a red flag, not something to silently accept).
- [ ] Check the per-city breakdown specifically: confirm no single city has drastically worse metrics than the rest (if one does, note it and consider whether that city has too little history, too many missing values, or genuinely different AQI dynamics).
- [ ] Hopsworks Model Registry UI shows the newly registered model version(s) with correct metadata attached.
- [ ] SHAP plot is generated and saved, and feature importances look directionally sensible (e.g., lag/PM2.5 features rank high).
- [ ] Test loading the registered model back from the registry in a separate throwaway script, run it against a sample row from **two different cities**, and confirm predictions differ sensibly based on the city feature (proves the model actually uses city, not ignoring it).

**Do not proceed to Phase 5 until every box above is checked.**