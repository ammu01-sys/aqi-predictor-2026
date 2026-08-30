import os
import pandas as pd
import numpy as np

# List of configured cities for one-hot encoding
SUPPORTED_CITIES = [
    "Lahore",
    "Karachi",
    "Islamabad",
    "Faisalabad",
    "Multan",
    "Peshawar",
    "Rawalpindi",
    "Gujranwala"
]

def add_time_features(df):
    """
    Adds time-based features to the DataFrame:
    hour, day_of_week, day_of_month, month, is_weekend (0/1).
    """
    df = df.copy()
    # Convert to pandas datetime if not already (timezone-aware UTC)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

    
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.weekday
    df["day_of_month"] = df["timestamp"].dt.day
    df["month"] = df["timestamp"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    
    return df

def add_city_encoding(df):
    """
    Adds one-hot encoded columns for the cities to the DataFrame.
    Creates columns: city_lahore, city_karachi, etc., populated with 0 or 1.
    This avoids Ridge Regression interpreting label-encoded integers as ordinal values.
    """
    df = df.copy()
    for city in SUPPORTED_CITIES:
        col_name = f"city_{city.lower()}"
        df[col_name] = (df["city"] == city).astype(int)
    return df

def add_lag_features(df):
    """
    Adds lag features for AQI: t-1h, t-3h, t-6h, t-24h.
    Lags are computed independently per city after sorting chronologically.
    Cold-start fallback: Fills missing lags with the current AQI value.
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

    df = df.sort_values(by=["city", "timestamp"])
    
    # Calculate lags grouped by city
    df["aqi_lag_1h"] = df.groupby("city")["aqi"].shift(1)
    df["aqi_lag_3h"] = df.groupby("city")["aqi"].shift(3)
    df["aqi_lag_6h"] = df.groupby("city")["aqi"].shift(6)
    df["aqi_lag_24h"] = df.groupby("city")["aqi"].shift(24)
    
    # Fallback to current AQI value if lag is missing (cold-start)
    # DELIBERATE CHOICE: During cold start (first run or new city with no history),
    # we assume persistence (the current AQI is the best estimate of the recent past)
    # and fill all lag variables with the current AQI value.
    df["aqi_lag_1h"] = df["aqi_lag_1h"].fillna(df["aqi"])
    df["aqi_lag_3h"] = df["aqi_lag_3h"].fillna(df["aqi"])
    df["aqi_lag_6h"] = df["aqi_lag_6h"].fillna(df["aqi"])
    df["aqi_lag_24h"] = df["aqi_lag_24h"].fillna(df["aqi"])
    
    return df

def add_rolling_features(df):
    """
    Adds rolling mean and standard deviation of AQI over 6h and 24h windows.
    Rolling stats are computed independently per city after sorting chronologically.
    Cold-start fallback: Mean falls back to current AQI, Std falls back to 0.0.
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

    df = df.sort_values(by=["city", "timestamp"])
    
    # Group by city and calculate rolling features
    grouped = df.groupby("city")["aqi"]
    
    # Note: rolling window includes the current row (closed="right" by default in pandas)
    df["aqi_rolling_mean_6h"] = grouped.rolling(window=6, min_periods=1).mean().reset_index(level=0, drop=True)
    df["aqi_rolling_std_6h"] = grouped.rolling(window=6, min_periods=1).std().reset_index(level=0, drop=True)
    
    df["aqi_rolling_mean_24h"] = grouped.rolling(window=24, min_periods=1).mean().reset_index(level=0, drop=True)
    df["aqi_rolling_std_24h"] = grouped.rolling(window=24, min_periods=1).std().reset_index(level=0, drop=True)
    
    # Fallback for cold-start (e.g. first few runs where count < window size or std is NaN)
    # DELIBERATE CHOICE: For rolling mean, we fall back to the current AQI value (persistence).
    # For rolling standard deviation, we fall back to 0.0, representing no historical variance.
    df["aqi_rolling_mean_6h"] = df["aqi_rolling_mean_6h"].fillna(df["aqi"])
    df["aqi_rolling_mean_24h"] = df["aqi_rolling_mean_24h"].fillna(df["aqi"])
    df["aqi_rolling_std_6h"] = df["aqi_rolling_std_6h"].fillna(0.0)
    df["aqi_rolling_std_24h"] = df["aqi_rolling_std_24h"].fillna(0.0)
    
    return df

def add_derived_features(df):
    """
    Adds AQI rate of change feature: (AQI_t - AQI_t-1) / AQI_t-1.
    Calculated independently per city.
    Cold-start fallback: Fills missing rates of change with 0.0.
    """
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

    df = df.sort_values(by=["city", "timestamp"])
    
    # Shift grouped by city to get AQI at t-1
    lag_aqi = df.groupby("city")["aqi"].shift(1)
    
    # Calculate change rate: (AQI - lag_AQI) / lag_AQI
    aqi_diff = df["aqi"] - lag_aqi
    
    # Replace zero with NaN to avoid division by zero issues
    denominator = lag_aqi.replace(0, np.nan)
    df["aqi_change_rate"] = (aqi_diff / denominator).fillna(0.0)
    
    # Replace infinite values and NaNs with 0.0 (fallback)
    # DELIBERATE CHOICE: During cold start, or when the previous value is 0,
    # the change rate is set to 0.0 to represent no rate change.
    df["aqi_change_rate"] = df["aqi_change_rate"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    
    return df

def engineer_all_features(df):
    """
    Runs all feature engineering steps sequentially.
    """
    df = add_time_features(df)
    df = add_city_encoding(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = add_derived_features(df)
    return df

if __name__ == "__main__":
    # Test script locally
    print("Testing feature_engineering.py with mock dataset...")
    
    # Create mock series of 3 hours for Lahore and Karachi
    mock_data = [
        {"city": "Lahore", "timestamp": "2026-07-30T12:00:00Z", "aqi": 100},
        {"city": "Lahore", "timestamp": "2026-07-30T13:00:00Z", "aqi": 120},
        {"city": "Lahore", "timestamp": "2026-07-30T14:00:00Z", "aqi": 150},
        {"city": "Karachi", "timestamp": "2026-07-30T12:00:00Z", "aqi": 80},
        {"city": "Karachi", "timestamp": "2026-07-30T13:00:00Z", "aqi": 90},
        {"city": "Karachi", "timestamp": "2026-07-30T14:00:00Z", "aqi": 85},
    ]
    df = pd.DataFrame(mock_data)
    
    df_engineered = engineer_all_features(df)
    print("\nEngineered DataFrame:")
    print(df_engineered[["city", "timestamp", "city_lahore", "city_karachi", "hour", "is_weekend", "aqi_lag_1h", "aqi_rolling_mean_6h", "aqi_rolling_std_6h", "aqi_change_rate"]])
