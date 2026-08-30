import os
import sys
import logging
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_cities_config, hopsworks_login, compute_aqi_from_pollutants
from src.feature_engineering import engineer_all_features
from src.feature_pipeline import cast_dataframe_schema

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


def fetch_city_historical_air_pollution(city_name, lat, lon, days=60):
    """
    Fetches hourly historical air pollution data (PM2.5, PM10, O3, NO2, SO2, CO)
    from OpenWeather Air Pollution History API for the specified number of days.

    AQI CONSISTENCY: AQI is computed directly via compute_aqi_from_pollutants() (US EPA
    piecewise linear formula) — no per-city scaling or calibration factors applied.
    This is intentional: the same formula and data source (OpenWeather pollutant
    concentrations in µg/m³) is used in both historical backfill and live ingestion
    (data_fetcher.py), ensuring end-to-end AQI consistency for model training/inference.

    aqicn_reference_aqi is set to None for historical rows because AQICN's native
    station AQI is not available from the OpenWeather historical API. This field is
    display-only and is not a model feature or training target.
    """
    if not OPENWEATHER_API_KEY:
        logger.error("OPENWEATHER_API_KEY is not set.")
        return pd.DataFrame()

    end_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=days)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    url = f"http://api.openweathermap.org/data/2.5/air_pollution/history?lat={lat}&lon={lon}&start={start_ts}&end={end_ts}&appid={OPENWEATHER_API_KEY}"
    
    try:
        logger.info(f"Fetching {days}-day historical air quality data for {city_name}...")
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        data = res.json()
        
        items = data.get("list", [])
        if not items:
            logger.warning(f"No historical items returned for {city_name}.")
            return pd.DataFrame()

        rows = []
        for item in items:
            dt_epoch = item.get("dt")
            comp = item.get("components", {})
            
            # UTC timestamp
            ts = datetime.fromtimestamp(dt_epoch, tz=timezone.utc)
            
            row_data = {
                "city": city_name,
                "timestamp": ts,
                "pm25": comp.get("pm2_5"),
                "pm10": comp.get("pm10"),
                "o3": comp.get("o3"),
                "no2": comp.get("no2"),
                "so2": comp.get("so2"),
                "co": comp.get("co"),
                # AQICN reference AQI not available for historical rows (display-only field)
                "aqicn_reference_aqi": None,
                # Weather variables unavailable from OW historical air pollution endpoint
                "temperature": None,
                "humidity": None,
                "wind_speed": None,
                "pressure": None,
                "aqi_source_ok": True,
                "weather_source_ok": False
            }
            
            # Compute US EPA AQI directly from pollutant concentrations — no scaling
            computed_aqi = compute_aqi_from_pollutants(row_data)
            row_data["aqi"] = computed_aqi if computed_aqi is not None else None
            
            rows.append(row_data)
            
        df = pd.DataFrame(rows)
        logger.info(f"Retrieved {len(df)} historical hourly rows for {city_name}.")
        return df

    except Exception as e:
        logger.error(f"Failed to fetch historical data for {city_name}: {e}")
        return pd.DataFrame()

def run_backfill(days=60, wipe_and_recreate=False):
    """
    Main backfill orchestrator:
    1. Fetches historical hourly data per city.
    2. Sorts by timestamp and computes features (lags, rolling stats, city one-hot).
    3. Computes targets (target_24h, target_48h, target_72h) from that city's own future rows.
    4. Combines all cities and inserts into Hopsworks Feature Store.

    Args:
        days: Number of historical days to backfill.
        wipe_and_recreate: If True, deletes the existing Feature Group before inserting
            (use only for intentional schema migrations — this permanently destroys all
            existing rows). If False (default), inserts/upserts into the existing group.

    SAFETY NOTE: Never set wipe_and_recreate=True in automated/scheduled pipeline runs.
    It is reserved exclusively for deliberate one-time schema migrations (e.g., adding
    a new column) and must be triggered manually via the --wipe CLI flag.
    """
    logger.info(f"Starting historical backfill for {days} days...")
    
    cities = load_cities_config()
    if not cities:
        logger.error("No cities loaded from config.")
        return

    city_backfill_dfs = []
    summary_counts = {}

    for city_info in cities:
        name = city_info["name"]
        lat = city_info["lat"]
        lon = city_info["lon"]

        try:
            logger.info(f"--- Processing backfill for city: {name} ---")
            raw_df = fetch_city_historical_air_pollution(name, lat, lon, days=days)
            if raw_df.empty:
                logger.warning(f"Skipping {name} due to empty historical fetch.")
                continue

            # Ensure UTC timestamp and sort chronologically
            raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"], utc=True)
            raw_df = raw_df.sort_values("timestamp", ascending=True).reset_index(drop=True)

            # Apply feature engineering (lags, rolling stats, time features, one-hot city)
            engineered_df = engineer_all_features(raw_df)

            # Compute future targets per city (look ahead 24h, 48h, 72h)
            engineered_df["target_24h"] = engineered_df["aqi"].shift(-24)
            engineered_df["target_48h"] = engineered_df["aqi"].shift(-48)
            engineered_df["target_72h"] = engineered_df["aqi"].shift(-72)

            # Drop the tail 72 hours where targets cannot be known
            valid_df = engineered_df.dropna(subset=["target_24h", "target_48h", "target_72h"]).copy()

            summary_counts[name] = len(valid_df)
            logger.info(f"Generated {len(valid_df)} valid feature+target rows for {name}.")
            city_backfill_dfs.append(valid_df)

        except Exception as e:
            logger.error(f"Error executing backfill loop for city {name}: {e}. Continuing with next city.")
            continue

    if not city_backfill_dfs:
        logger.error("No valid historical data generated across any city.")
        return

    # Combine all city dataframes
    full_backfill_df = pd.concat(city_backfill_dfs, ignore_index=True)
    full_backfill_df = cast_dataframe_schema(full_backfill_df)

    logger.info(f"\n==================================================")
    logger.info(f"Total historical rows ready for Hopsworks insert: {len(full_backfill_df)}")
    for c_name, count in summary_counts.items():
        logger.info(f" - {c_name}: {count} rows")
    logger.info(f"==================================================\n")

    # Log in to Hopsworks & insert into Feature Store
    try:
        project = hopsworks_login()
        fs = project.get_feature_store()
        
        if wipe_and_recreate:
            # INTENTIONAL SCHEMA MIGRATION: delete existing Feature Group to apply new schema.
            # WARNING: This permanently destroys ALL existing rows. Only invoke via --wipe flag.
            try:
                old_fg = fs.get_feature_group(name="aqi_features", version=1)
                if old_fg:
                    logger.warning("[--wipe] Deleting 'aqi_features' (v1) for schema migration. ALL EXISTING ROWS WILL BE LOST.")
                    old_fg.delete()
                    logger.info("[--wipe] Deleted old Feature Group successfully.")
            except Exception as e:
                logger.info(f"[--wipe] Feature group deletion note: {e}")

        aqi_fg = fs.get_or_create_feature_group(
            name="aqi_features",
            version=1,
            primary_key=["city", "timestamp"],
            event_time="timestamp",
            description="Hourly air quality and weather features + targets for 8 Pakistani cities",
            online_enabled=False,
            time_travel_format="HUDI"
        )

        logger.info("Inserting historical backfill dataset into Hopsworks 'aqi_features' Feature Group...")
        aqi_fg.insert(full_backfill_df, write_options={"wait_for_job": False})
        logger.info("Backfill insertion job submitted successfully to Hopsworks!")
    except Exception as e:
        logger.error(f"Failed to insert backfill data into Hopsworks: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AQI Historical Backfill")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help=(
            "DESTRUCTIVE: Delete and recreate the 'aqi_features' Feature Group before inserting. "
            "Use ONLY for intentional schema migrations. Permanently destroys all existing rows."
        )
    )
    parser.add_argument(
        "--days",
        type=int,
        default=60,
        help="Number of historical days to backfill (default: 60)."
    )
    args = parser.parse_args()

    if args.wipe:
        logger.warning("=" * 60)
        logger.warning("--wipe FLAG DETECTED: This will permanently delete all")
        logger.warning("existing rows in the 'aqi_features' Feature Group.")
        logger.warning("This is a ONE-TIME intentional schema migration.")
        logger.warning("DO NOT use this flag in automated/scheduled pipeline runs.")
        logger.warning("=" * 60)

    run_backfill(days=args.days, wipe_and_recreate=args.wipe)
