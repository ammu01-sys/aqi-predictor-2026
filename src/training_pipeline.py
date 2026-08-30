import os
import sys
import logging
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
from datetime import datetime, timezone
from dotenv import load_dotenv

from sklearn.linear_model import RidgeCV
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import hopsworks_login

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class AQIPredictorModelWrapper:
    """
    Production model wrapper artifact ensuring reproducible, leak-free inference.
    Preserves exact feature ordering, scaler, city encoding, and weather-rejection assertion.
    Predicts full AQI via baseline + residual delta.
    """
    def __init__(self, model, scaler, feature_names, encoding_type, horizon, is_residual=True, metrics=None):
        self.model = model
        self.scaler = scaler
        self.feature_names = feature_names
        self.encoding_type = encoding_type
        self.horizon = horizon
        self.is_residual = is_residual
        self.metrics = metrics or {}
        self.created_at = datetime.now(timezone.utc).isoformat()

    def predict(self, df_features: pd.DataFrame) -> np.ndarray:
        df = df_features.copy()
        
        # Enforce safety check: reject weather columns for this model version (decision #10)
        forbidden_weather = ["temperature", "humidity", "wind_speed", "pressure"]
        present_weather = [c for c in forbidden_weather if c in df.columns and df[c].notnull().any()]
        if present_weather:
            raise ValueError(
                f"Weather-null mismatch safeguard: Model '{self.horizon}' was trained with zero weather features. "
                f"Passing live weather columns {present_weather} is strictly rejected until a weather-inclusive retrain."
            )

        # Align features
        missing_cols = [c for c in self.feature_names if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required feature columns for prediction: {missing_cols}")

        X = df[self.feature_names].copy()
        
        if self.scaler is not None:
            X = self.scaler.transform(X)

        raw_pred = self.model.predict(X)
        if self.is_residual:
            # Full AQI = current AQI + predicted delta
            return df["aqi"].values + raw_pred
        return raw_pred


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Pure-Python markdown table generator requiring no external dependencies."""
    headers = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def load_dataset_from_hopsworks():
    """
    Loads aqi_features v1 from Hopsworks Feature Store and verifies timestamp alignment across cities.
    """
    logger.info("Connecting to Hopsworks Feature Store to load aqi_features (v1)...")
    project = hopsworks_login()
    fs = project.get_feature_store()
    fg = fs.get_feature_group("aqi_features", version=1)
    
    df = fg.read()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(by=["city", "timestamp"]).reset_index(drop=True)
    
    # Filter out recent live hourly rows that do not have future targets populated yet
    initial_len = len(df)
    df = df.dropna(subset=["target_24h", "target_48h", "target_72h"]).copy().reset_index(drop=True)
    dropped_rows = initial_len - len(df)
    if dropped_rows > 0:
        logger.info(f"Filtered out {dropped_rows} recent live rows with unobserved future targets.")

    logger.info(f"Loaded training dataset of shape {df.shape} from Feature Store.")
    
    # Assert timestamp alignment precondition across cities
    cities = df["city"].unique().tolist()
    print("\n--- Per-City Timestamp Range Precondition Table ---")
    ts_ranges = {}
    for city in cities:
        c_df = df[df["city"] == city]
        min_ts = c_df["timestamp"].min()
        max_ts = c_df["timestamp"].max()
        ts_ranges[city] = (min_ts, max_ts)
        print(f"City: {city:12s} | Rows: {len(c_df):5d} | Min: {min_ts} | Max: {max_ts}")

    # Check that min/max timestamps match within a reasonable 24h boundary
    all_mins = [r[0] for r in ts_ranges.values()]
    all_maxs = [r[1] for r in ts_ranges.values()]
    min_diff = max(all_mins) - min(all_mins)
    max_diff = max(all_maxs) - min(all_maxs)
    
    assert min_diff <= pd.Timedelta(hours=24), f"City minimum timestamps differ significantly: {min_diff}"
    assert max_diff <= pd.Timedelta(hours=24), f"City maximum timestamps differ significantly: {max_diff}"
    logger.info("Timestamp alignment precondition verified successfully across all cities.\n")
    
    return project, df


def prepare_feature_matrices(df: pd.DataFrame):
    """
    Prepares leakage-free feature sets (one-hot vs integer city representations)
    excluding all targets, weather nulls, and metadata flags.
    """
    df = df.copy()
    
    # Add cyclical hour features for diurnal patterns
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
    
    # Base predictive feature columns
    base_features = [
        "pm25", "pm10", "o3", "no2", "so2", "co", "aqi",
        "hour", "hour_sin", "hour_cos", "day_of_week", "day_of_month", "month", "is_weekend",
        "aqi_lag_1h", "aqi_lag_3h", "aqi_lag_6h", "aqi_lag_24h",
        "aqi_rolling_mean_6h", "aqi_rolling_std_6h",
        "aqi_rolling_mean_24h", "aqi_rolling_std_24h",
        "aqi_change_rate"
    ]
    
    # City One-Hot columns
    city_onehot_cols = [c for c in df.columns if c.startswith("city_")]
    features_onehot = base_features + city_onehot_cols
    
    # City Integer Encoding (for comparison with one-hot)
    city_list = sorted(df["city"].unique().tolist())
    city_to_int = {city: i for i, city in enumerate(city_list)}
    df["city_code"] = df["city"].map(city_to_int)
    features_integer = base_features + ["city_code"]
    
    # Targets
    target_cols = ["target_24h", "target_48h", "target_72h"]
    
    # Verify zero target leakage into feature lists
    for t_col in target_cols:
        assert t_col not in features_onehot, f"Leakage: {t_col} found in features_onehot!"
        assert t_col not in features_integer, f"Leakage: {t_col} found in features_integer!"
        
    return df, features_onehot, features_integer, city_to_int


def split_data_chronologically(df: pd.DataFrame):
    """
    Strict global chronological split (70% Train, 15% Val, 15% Test)
    based on global UTC timestamp boundaries.
    """
    df = df.sort_values("timestamp").reset_index(drop=True)
    min_ts = df["timestamp"].min()
    max_ts = df["timestamp"].max()
    duration = max_ts - min_ts
    
    cutoff_val = min_ts + duration * 0.70
    cutoff_test = min_ts + duration * 0.85
    
    train_mask = df["timestamp"] < cutoff_val
    val_mask = (df["timestamp"] >= cutoff_val) & (df["timestamp"] < cutoff_test)
    test_mask = df["timestamp"] >= cutoff_test
    
    train_df = df[train_mask].copy()
    val_df = df[val_mask].copy()
    test_df = df[test_mask].copy()
    
    print("==================================================")
    print("GLOBAL CHRONOLOGICAL SPLIT SUMMARY")
    print("==================================================")
    print(f"Full Date Range: {min_ts.strftime('%Y-%m-%d %H:%M')} to {max_ts.strftime('%Y-%m-%d %H:%M')}")
    print(f"TRAIN Set : {len(train_df):5d} rows | {train_df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to {train_df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}")
    print(f"VAL Set   : {len(val_df):5d} rows | {val_df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to {val_df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}")
    print(f"TEST Set  : {len(test_df):5d} rows | {test_df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to {test_df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}")
    print("==================================================\n")
    
    return train_df, val_df, test_df, (min_ts, cutoff_val, cutoff_test, max_ts)


def calculate_metrics(y_true, y_pred):
    """Calculates RMSE, MAE, R2."""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return round(rmse, 2), round(mae, 2), round(r2, 3)


def run_training_pipeline():
    logger.info("Starting Phase 4 Model Training Pipeline...")
    
    # 1. Load Data
    project, df_raw = load_dataset_from_hopsworks()
    
    # 2. Prepare Features & Encoding
    df, features_onehot, features_integer, city_to_int = prepare_feature_matrices(df_raw)
    
    # 3. Chronological Split
    train_df, val_df, test_df, split_cutoffs = split_data_chronologically(df)
    
    horizons = ["target_24h", "target_48h", "target_72h"]
    all_results = []
    winning_models_info = {}
    
    # Ensure directories exist
    os.makedirs("models", exist_ok=True)
    os.makedirs("docs", exist_ok=True)
    
    for horizon in horizons:
        print(f"\n##################################################")
        print(f"TRAINING & EVALUATION FOR HORIZON: {horizon.upper()}")
        print(f"##################################################")
        
        y_train = train_df[horizon].values
        y_val = val_df[horizon].values
        y_test = test_df[horizon].values
        
        # Residual delta targets (delta = y - current_aqi)
        delta_train = y_train - train_df["aqi"].values
        delta_test = y_test - test_df["aqi"].values
        
        # 1. Persistence Baseline: prediction = current AQI
        y_pred_persist = test_df["aqi"].values
        persist_rmse, persist_mae, persist_r2 = calculate_metrics(y_test, y_pred_persist)
        
        all_results.append({"model": "Persistence Baseline", "encoding": "none", "horizon": horizon, "city": "OVERALL", "RMSE": persist_rmse, "MAE": persist_mae, "R2": persist_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_persist[c_mask])
            all_results.append({"model": "Persistence Baseline", "encoding": "none", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})
            
        # 2. Ridge Regression (One-Hot + StandardScaler on Residual Delta)
        scaler_ridge = StandardScaler()
        X_train_oh_scaled = scaler_ridge.fit_transform(train_df[features_onehot])
        X_test_oh_scaled = scaler_ridge.transform(test_df[features_onehot])
        
        ridge_model = RidgeCV(alphas=[0.1, 1.0, 10.0, 50.0, 100.0, 500.0, 1000.0, 5000.0])
        ridge_model.fit(X_train_oh_scaled, delta_train)
        pred_delta_ridge = ridge_model.predict(X_test_oh_scaled)
        y_pred_ridge = test_df["aqi"].values + pred_delta_ridge
        
        r_rmse, r_mae, r_r2 = calculate_metrics(y_test, y_pred_ridge)
        all_results.append({"model": "Ridge Regression", "encoding": "one_hot", "horizon": horizon, "city": "OVERALL", "RMSE": r_rmse, "MAE": r_mae, "R2": r_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_ridge[c_mask])
            all_results.append({"model": "Ridge Regression", "encoding": "one_hot", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})

        # 3. XGBoost (One-Hot on Residual Delta)
        xgb_oh = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.025, subsample=0.8, colsample_bytree=0.8, reg_alpha=1.0, reg_lambda=5.0, random_state=42, n_jobs=-1)
        xgb_oh.fit(train_df[features_onehot], delta_train)
        pred_delta_xgb_oh = xgb_oh.predict(test_df[features_onehot])
        y_pred_xgb_oh = test_df["aqi"].values + pred_delta_xgb_oh
        xgb_oh_rmse, xgb_oh_mae, xgb_oh_r2 = calculate_metrics(y_test, y_pred_xgb_oh)
        all_results.append({"model": "XGBoost", "encoding": "one_hot", "horizon": horizon, "city": "OVERALL", "RMSE": xgb_oh_rmse, "MAE": xgb_oh_mae, "R2": xgb_oh_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_xgb_oh[c_mask])
            all_results.append({"model": "XGBoost", "encoding": "one_hot", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})

        # 4. XGBoost (Integer Encoding on Residual Delta)
        xgb_int = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.025, subsample=0.8, colsample_bytree=0.8, reg_alpha=1.0, reg_lambda=5.0, random_state=42, n_jobs=-1)
        xgb_int.fit(train_df[features_integer], delta_train)
        pred_delta_xgb_int = xgb_int.predict(test_df[features_integer])
        y_pred_xgb_int = test_df["aqi"].values + pred_delta_xgb_int
        xgb_int_rmse, xgb_int_mae, xgb_int_r2 = calculate_metrics(y_test, y_pred_xgb_int)
        all_results.append({"model": "XGBoost", "encoding": "integer", "horizon": horizon, "city": "OVERALL", "RMSE": xgb_int_rmse, "MAE": xgb_int_mae, "R2": xgb_int_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_xgb_int[c_mask])
            all_results.append({"model": "XGBoost", "encoding": "integer", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})

        # 5. Random Forest (One-Hot on Residual Delta)
        rf_oh = RandomForestRegressor(n_estimators=120, max_depth=5, min_samples_leaf=8, random_state=42, n_jobs=-1)
        rf_oh.fit(train_df[features_onehot], delta_train)
        pred_delta_rf_oh = rf_oh.predict(test_df[features_onehot])
        y_pred_rf_oh = test_df["aqi"].values + pred_delta_rf_oh
        rf_oh_rmse, rf_oh_mae, rf_oh_r2 = calculate_metrics(y_test, y_pred_rf_oh)
        all_results.append({"model": "Random Forest", "encoding": "one_hot", "horizon": horizon, "city": "OVERALL", "RMSE": rf_oh_rmse, "MAE": rf_oh_mae, "R2": rf_oh_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_rf_oh[c_mask])
            all_results.append({"model": "Random Forest", "encoding": "one_hot", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})

        # 6. Random Forest (Integer Encoding on Residual Delta)
        rf_int = RandomForestRegressor(n_estimators=120, max_depth=5, min_samples_leaf=8, random_state=42, n_jobs=-1)
        rf_int.fit(train_df[features_integer], delta_train)
        pred_delta_rf_int = rf_int.predict(test_df[features_integer])
        y_pred_rf_int = test_df["aqi"].values + pred_delta_rf_int
        rf_int_rmse, rf_int_mae, rf_int_r2 = calculate_metrics(y_test, y_pred_rf_int)
        all_results.append({"model": "Random Forest", "encoding": "integer", "horizon": horizon, "city": "OVERALL", "RMSE": rf_int_rmse, "MAE": rf_int_mae, "R2": rf_int_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_rf_int[c_mask])
            all_results.append({"model": "Random Forest", "encoding": "integer", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})

        # 7. Neural Network / MLP (One-Hot + StandardScaler on Residual Delta)
        scaler_mlp = StandardScaler()
        X_train_mlp = scaler_mlp.fit_transform(train_df[features_onehot])
        X_test_mlp = scaler_mlp.transform(test_df[features_onehot])
        
        mlp_model = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500, alpha=0.1, learning_rate_init=0.003, random_state=42, early_stopping=True)
        mlp_model.fit(X_train_mlp, delta_train)
        pred_delta_mlp = mlp_model.predict(X_test_mlp)
        y_pred_mlp = test_df["aqi"].values + pred_delta_mlp
        mlp_rmse, mlp_mae, mlp_r2 = calculate_metrics(y_test, y_pred_mlp)
        all_results.append({"model": "Neural Network (MLP)", "encoding": "one_hot", "horizon": horizon, "city": "OVERALL", "RMSE": mlp_rmse, "MAE": mlp_mae, "R2": mlp_r2})
        for city in sorted(test_df["city"].unique()):
            c_mask = test_df["city"] == city
            c_rmse, c_mae, c_r2 = calculate_metrics(y_test[c_mask], y_pred_mlp[c_mask])
            all_results.append({"model": "Neural Network (MLP)", "encoding": "one_hot", "horizon": horizon, "city": city, "RMSE": c_rmse, "MAE": c_mae, "R2": c_r2})

        # Candidate Model Objects
        candidates = {
            "Persistence Baseline": {"model": None, "scaler": None, "features": ["aqi"], "encoding": "none", "rmse": persist_rmse, "mae": persist_mae, "r2": persist_r2},
            "Ridge Regression": {"model": ridge_model, "scaler": scaler_ridge, "features": features_onehot, "encoding": "one_hot", "rmse": r_rmse, "mae": r_mae, "r2": r_r2},
            "XGBoost (one_hot)": {"model": xgb_oh, "scaler": None, "features": features_onehot, "encoding": "one_hot", "rmse": xgb_oh_rmse, "mae": xgb_oh_mae, "r2": xgb_oh_r2},
            "XGBoost (integer)": {"model": xgb_int, "scaler": None, "features": features_integer, "encoding": "integer", "rmse": xgb_int_rmse, "mae": xgb_int_mae, "r2": xgb_int_r2},
            "Random Forest (one_hot)": {"model": rf_oh, "scaler": None, "features": features_onehot, "encoding": "one_hot", "rmse": rf_oh_rmse, "mae": rf_oh_mae, "r2": rf_oh_r2},
            "Random Forest (integer)": {"model": rf_int, "scaler": None, "features": features_integer, "encoding": "integer", "rmse": rf_int_rmse, "mae": rf_int_mae, "r2": rf_int_r2},
            "Neural Network (MLP)": {"model": mlp_model, "scaler": scaler_mlp, "features": features_onehot, "encoding": "one_hot", "rmse": mlp_rmse, "mae": mlp_mae, "r2": mlp_r2},
        }

        # Model Selection Rule:
        ml_candidates = {k: v for k, v in candidates.items() if k != "Persistence Baseline"}
        best_ml_name = min(ml_candidates, key=lambda k: ml_candidates[k]["rmse"])
        best_ml = ml_candidates[best_ml_name]
        
        # Check if best ML model beats Persistence
        if best_ml["rmse"] < persist_rmse:
            winner_name = best_ml_name
            winner_data = best_ml
            is_ml_winner = True
            print(f"-> WINNER for {horizon}: {winner_name} (RMSE: {winner_data['rmse']} vs Persistence: {persist_rmse})")
        else:
            winner_name = "Persistence Baseline"
            winner_data = candidates["Persistence Baseline"]
            is_ml_winner = False
            print(f"-> WINNER for {horizon}: Persistence Baseline retained (Persistence RMSE: {persist_rmse} vs Best ML: {best_ml['rmse']})")

        winning_models_info[horizon] = {
            "winner_name": winner_name,
            "winner_data": winner_data,
            "is_ml_winner": is_ml_winner
        }

        # Generate SHAP explanations for ML winner
        if is_ml_winner:
            print(f"Generating SHAP summary for winning model: {winner_name}...")
            winner_model = winner_data["model"]
            winner_feats = winner_data["features"]
            sample_X = test_df[winner_feats].sample(min(300, len(test_df)), random_state=42)
            
            try:
                if "Forest" in winner_name or "XGBoost" in winner_name:
                    explainer = shap.TreeExplainer(winner_model)
                    shap_values = explainer.shap_values(sample_X)
                elif "Ridge" in winner_name:
                    X_sample_scaled = winner_data["scaler"].transform(sample_X)
                    explainer = shap.LinearExplainer(winner_model, X_sample_scaled)
                    shap_values = explainer.shap_values(X_sample_scaled)
                else:
                    X_sample_scaled = winner_data["scaler"].transform(sample_X)
                    explainer = shap.KernelExplainer(winner_model.predict, shap.sample(X_sample_scaled, 50))
                    shap_values = explainer.shap_values(X_sample_scaled)

                plt.figure(figsize=(10, 6))
                shap.summary_plot(shap_values, sample_X, feature_names=winner_feats, show=False)
                shap_path = f"docs/shap_summary_{horizon.replace('target_', '')}.png"
                plt.title(f"SHAP Feature Importance ({winner_name} - {horizon})", fontsize=13, fontweight="bold")
                plt.tight_layout()
                plt.savefig(shap_path, dpi=200, bbox_inches="tight")
                plt.close()
                print(f"Saved SHAP plot to {shap_path}")
            except Exception as e:
                logger.warning(f"SHAP calculation note for {horizon}: {e}")

    # Create Comparison DataFrame
    results_df = pd.DataFrame(all_results)
    
    # Save comparison table to docs/model_comparison.md
    print("\n==================================================")
    print("MODEL COMPARISON TABLE (OVERALL RESULTS)")
    print("==================================================")
    overall_df = results_df[results_df["city"] == "OVERALL"].sort_values(by=["horizon", "RMSE"])
    print(overall_df.to_string(index=False))
    
    md_table_path = "docs/model_comparison.md"
    with open(md_table_path, "w") as f:
        f.write("# Model Comparison Table across Forecast Horizons\n\n")
        f.write("Evaluation conducted on untouched chronological test set (last 15% of 60-day historical time series).\n\n")
        f.write("## Overall Horizon Comparison\n\n")
        f.write(dataframe_to_markdown(overall_df))
        f.write("\n\n## Per-City Detailed Breakdown\n\n")
        f.write(dataframe_to_markdown(results_df))
        f.write("\n")
    logger.info(f"Saved comprehensive model comparison table to {md_table_path}")

    # Register Winning Models to Hopsworks Model Registry
    logger.info("\nRegistering winning models to Hopsworks Model Registry...")
    mr = project.get_model_registry()
    
    for horizon, win_info in winning_models_info.items():
        w_name = win_info["winner_name"]
        w_data = win_info["winner_data"]
        is_ml = win_info["is_ml_winner"]
        
        reg_model_name = f"aqi_model_{horizon.replace('target_', '')}"
        artifact_path = f"models/{reg_model_name}.pkl"
        
        if is_ml:
            wrapper = AQIPredictorModelWrapper(
                model=w_data["model"],
                scaler=w_data["scaler"],
                feature_names=w_data["features"],
                encoding_type=w_data["encoding"],
                horizon=horizon,
                is_residual=True,
                metrics={"RMSE": w_data["rmse"], "MAE": w_data["mae"], "R2": w_data["r2"]}
            )
            joblib.dump(wrapper, artifact_path)
            
            # Register in Hopsworks
            try:
                hw_model = mr.python.create_model(
                    name=reg_model_name,
                    metrics={"RMSE": w_data["rmse"], "MAE": w_data["mae"], "R2": w_data["r2"]},
                    description=f"Winning {w_name} model for {horizon} predicting multi-city AQI in Pakistan",
                )
                hw_model.save(artifact_path)
                logger.info(f"Registered '{reg_model_name}' (v{hw_model.version}) successfully in Hopsworks Model Registry.")
            except Exception as e:
                logger.error(f"Failed to register model {reg_model_name} in Hopsworks: {e}")
        else:
            logger.info(f"Horizon {horizon} won by Persistence Baseline. No ML artifact registered.")

    print("\n==================================================")
    print("PHASE 4 MODEL TRAINING PIPELINE COMPLETED SUCCESSFULLY!")
    print("==================================================")
    
    return results_df, winning_models_info

if __name__ == "__main__":
    run_training_pipeline()
