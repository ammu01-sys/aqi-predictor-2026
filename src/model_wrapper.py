"""
src/model_wrapper.py
--------------------
Production model wrapper for the AQI Predictor.

Kept in its own module so that:
  - joblib-pickled artifacts can be loaded from ANY script (not just training_pipeline.py)
  - The class path resolves to `src.model_wrapper.AQIPredictorModelWrapper`
    instead of the old `__main__.AQIPredictorModelWrapper` which required the
    training script to be the active __main__ module at load time.

Import this class wherever you need to load or create a model artifact.
"""

from datetime import datetime, timezone
import numpy as np
import pandas as pd


class AQIPredictorModelWrapper:
    """
    Production model wrapper artifact ensuring reproducible, leak-free inference.
    Preserves exact feature ordering, scaler, city encoding, and weather-rejection assertion.
    Predicts full AQI via baseline + residual delta.
    """

    def __init__(self, model, scaler, feature_names, encoding_type, horizon,
                 is_residual=True, metrics=None):
        self.model = model
        self.scaler = scaler
        self.feature_names = feature_names
        self.encoding_type = encoding_type
        self.horizon = horizon
        self.is_residual = is_residual
        self.metrics = metrics or {}
        self.created_at = datetime.now(timezone.utc).isoformat()

    def predict(self, df_features: pd.DataFrame) -> np.ndarray:
        """
        Run inference on a prepared feature DataFrame.

        The DataFrame must:
          - Contain all columns listed in self.feature_names
          - Have weather columns (temperature, humidity, wind_speed, pressure)
            set to NaN or absent — this model was trained without weather features
            (Decision #10) and will raise if live weather values are passed.
          - Contain an 'aqi' column when is_residual=True (used to reconstruct
            the final AQI from the predicted residual delta).
        """
        df = df_features.copy()

        # Safety guard: reject weather columns for this model version (Decision #10)
        forbidden_weather = ["temperature", "humidity", "wind_speed", "pressure"]
        present_weather = [
            c for c in forbidden_weather
            if c in df.columns and df[c].notnull().any()
        ]
        if present_weather:
            raise ValueError(
                f"Weather-null mismatch safeguard: Model '{self.horizon}' was trained "
                f"with zero weather features. Passing live weather columns "
                f"{present_weather} is strictly rejected until a weather-inclusive retrain."
            )

        # Feature alignment
        missing_cols = [c for c in self.feature_names if c not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Missing required feature columns for prediction: {missing_cols}"
            )

        X = df[self.feature_names].copy()

        if self.scaler is not None:
            X = self.scaler.transform(X)

        raw_pred = self.model.predict(X)

        if self.is_residual:
            # Full AQI = current AQI + predicted residual delta
            return df["aqi"].values + raw_pred

        return raw_pred

    def __repr__(self):
        model_type = type(self.model).__name__ if self.model is not None else "None"
        return (
            f"AQIPredictorModelWrapper("
            f"horizon={self.horizon!r}, "
            f"model={model_type}, "
            f"encoding={self.encoding_type!r}, "
            f"features={len(self.feature_names)}, "
            f"metrics={self.metrics})"
        )
