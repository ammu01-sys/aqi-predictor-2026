import os

import sys
import logging
import pandas as pd
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_cities_config, hopsworks_login
from src.data_fetcher import fetch_combined_data
from src.feature_engineering import engineer_all_features

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def cast_dataframe_schema(df):
    """
    Explicitly casts all columns to ensure Hopsworks infers correct types on first insert.
    """
    df = df.copy()
    
    # Cast timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Text/categorical
    df["city"] = df["city"].astype(str)
    
    # Floats
    float_cols = [
        "pm25", "pm10", "o3", "no2", "so2", "co", "aqi",
        "aqicn_reference_aqi",  # Display-only AQICN native value; not a model feature or target
        "temperature", "humidity", "wind_speed", "pressure",
        "aqi_lag_1h", "aqi_lag_3h", "aqi_lag_6h", "aqi_lag_24h",
        "aqi_rolling_mean_6h", "aqi_rolling_std_6h",
        "aqi_rolling_mean_24h", "aqi_rolling_std_24h",
        "aqi_change_rate",
        "target_24h", "target_48h", "target_72h"
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
            
    # Integers
    int_cols = ["hour", "day_of_week", "day_of_month", "month", "is_weekend"]
    
    # Add one-hot encoded city columns dynamically
    for col in df.columns:
        if col.startswith("city_"):
            int_cols.append(col)
            
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            
    # Booleans
    bool_cols = ["aqi_source_ok", "weather_source_ok"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(bool)
            
    return df

def fetch_recent_history(fs, aqi_fg, city, limit=30):
    """
    Queries Hopsworks Feature Store for the last N hours of data for a specific city.
    Tries SQL query first, falls back to read().
    """
    # 1. SQL check
    try:
        query_str = f"SELECT * FROM `{aqi_fg.name}_{aqi_fg.version}` WHERE city = '{city}' ORDER BY timestamp DESC LIMIT {limit}"
        logger.info(f"Querying history via SQL for {city}: {query_str}")
        df = fs.sql(query_str)
        if df is not None and not df.empty:
            logger.info(f"Successfully retrieved {len(df)} historical rows via SQL for {city}.")
            return df
    except Exception as e:
        logger.warning(f"SQL history query failed for {city}: {e}. Trying read() fallback...")
        
    # 2. read() check
    try:
        df = aqi_fg.read()
        if df is not None and not df.empty:
            df = df[df["city"] == city]
            df = df.sort_values(by="timestamp", ascending=False).head(limit)
            logger.info(f"Successfully retrieved {len(df)} historical rows via read() for {city}.")
            return df
    except Exception as e:
        logger.warning(f"read() fallback failed for {city}: {e}")
        
    return pd.DataFrame()

def run_pipeline():
    logger.info("Starting hourly feature pipeline...")
    
    # 1. Load config
    try:
        cities = load_cities_config()
    except Exception as e:
        logger.error(f"Failed to load cities config: {e}")
        return
        
    # 2. Log in to Hopsworks
    try:
        project = hopsworks_login()
        fs = project.get_feature_store()
        logger.info("Logged in to Hopsworks Feature Store successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to Hopsworks: {e}")
        return
        
    # 3. Get or create the Feature Group
    try:
        aqi_fg = fs.get_or_create_feature_group(
            name="aqi_features",
            version=1,
            primary_key=["city", "timestamp"],
            event_time="timestamp",
            description="Hourly air quality and weather features for 8 Pakistani cities",
            online_enabled=False,
            time_travel_format="HUDI"
        )
        logger.info("Successfully fetched or defined aqi_features Feature Group.")
    except Exception as e:
        logger.error(f"Failed to get or create Feature Group: {e}")
        return

    # Collect engineered rows across all cities
    new_rows = []
    
    # 4. Fetch and engineer data for each city
    for city_info in cities:
        name = city_info["name"]
        lat = city_info["lat"]
        lon = city_info["lon"]
        
        logger.info(f"Processing city: {name} ({lat}, {lon})")
        
        try:
            # A. Fetch current data
            current_data = fetch_combined_data(name, lat, lon)
            if not current_data:
                logger.warning(f"No current data retrieved for {name}. Skipping.")
                continue
                
            current_df = pd.DataFrame([current_data])
            
            # B. Read history (last 30 hours)
            history_df = fetch_recent_history(fs, aqi_fg, name, limit=30)

            # C. Combine and engineer
            if not history_df.empty:
                # Ensure timestamps are aligned and types match
                current_df["timestamp"] = pd.to_datetime(current_df["timestamp"], utc=True)
                history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], utc=True)

                # Combine
                combined_df = pd.concat([history_df, current_df], ignore_index=True)
                
                # Drop duplicate timestamps for resilience
                combined_df = combined_df.drop_duplicates(subset=["city", "timestamp"], keep="last")
            else:
                logger.info(f"No history found for {name}. Triggering cold start.")
                combined_df = current_df
                
            # D. Apply feature engineering
            engineered_df = engineer_all_features(combined_df)
            
            # E. Extract the newest row (the one we just fetched)
            # Engineered functions sort values by ["city", "timestamp"] ascending
            city_engineered = engineered_df[engineered_df["city"] == name]
            newest_row = city_engineered.tail(1)

            if name == "Lahore":
                logger.info(f"Lahore AQI this run: {newest_row['aqi'].values[0]}")

            new_rows.append(newest_row)
            logger.info(f"Successfully processed features for {name}.")
            
        except Exception as e:
            logger.error(f"Error processing city {name}: {e}. Continuing with remaining cities.")
            
    # 5. Insert combined rows into Hopsworks
    if new_rows:
        try:
            insert_df = pd.concat(new_rows, ignore_index=True)
            # Standardize column types to prevent schema issues
            insert_df = cast_dataframe_schema(insert_df)
            
            logger.info(f"Inserting {len(insert_df)} rows into aqi_features Feature Group...")
            # Perform insertion
            aqi_fg.insert(insert_df, write_options={"wait_for_job": False})
            logger.info("Feature insertion job submitted successfully to Hopsworks.")
        except Exception as e:
            logger.error(f"Failed to insert features into Hopsworks: {e}")
    else:
        logger.warning("No new feature rows to insert.")

if __name__ == "__main__":
    run_pipeline()
