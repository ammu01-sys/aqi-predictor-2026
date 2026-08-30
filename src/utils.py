import os
from datetime import datetime, timezone, timedelta
import yaml

def load_cities_config(config_path="config/cities.yaml"):
    """
    Loads the city list from config_path (YAML format) and returns a list of dictionaries.
    Each dictionary contains 'name', 'lat', and 'lon'.
    """
    # If the file doesn't exist, search from workspace root.
    if not os.path.exists(config_path):
        # Fallback to check relative to root directory
        possible_paths = [
            config_path,
            os.path.join(os.path.dirname(os.path.dirname(__file__)), config_path),
            os.path.join(os.getcwd(), config_path)
        ]
        for p in possible_paths:
            if os.path.exists(p):
                config_path = p
                break
        else:
            raise FileNotFoundError(f"Config file not found. Tried paths: {possible_paths}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("cities", [])

def round_timestamp_to_hour(ts):
    """
    Rounds a timestamp to the nearest hour.
    ts can be:
      - datetime object
      - int/float representing epoch seconds
      - string (ISO format or YYYY-MM-DD HH:MM:SS with or without offset)
    Returns a timezone-aware (UTC) datetime object with minute, second, and microsecond set to 0.

    CRITICAL TIMEZONE HANDLING:
    If the input contains a local station timezone offset (e.g. +05:00 for PKT),
    astimezone(timezone.utc) or pd.to_datetime(ts, utc=True) MUST be used to shift
    the time to true UTC. Blindly using replace(tzinfo=timezone.utc) without adjusting
    hours mislabels local time as UTC, introducing a ~5 hour offset error.
    """
    if isinstance(ts, (int, float)):
        # Convert epoch seconds to datetime (UTC)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(ts, str):
        # Use pandas for robust ISO and offset-aware parsing with conversion to UTC
        try:
            import pandas as pd
            dt = pd.to_datetime(ts, utc=True).to_pydatetime()
        except Exception:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
            except Exception:
                raise ValueError(f"Could not parse timestamp string: {ts}")
    elif isinstance(ts, datetime):
        dt = ts
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Convert aware datetime (e.g. UTC+5) to true UTC (+00:00)
            dt = dt.astimezone(timezone.utc)
    else:
        raise TypeError(f"Unsupported timestamp type: {type(ts)}")
        
    # Round to nearest hour
    if dt.minute >= 30:
        dt = dt + timedelta(hours=1)
    
    return dt.replace(minute=0, second=0, microsecond=0)

def compute_aqi_from_pollutants(pollutants: dict) -> int:
    """
    Computes US EPA AQI for PM2.5 and PM10 and returns the maximum AQI value.
    If no pollutant concentrations are available, returns None.
    """
    pm25 = pollutants.get("pm25")
    pm10 = pollutants.get("pm10")
    
    aqi_values = []
    
    if pm25 is not None:
        try:
            val = float(pm25)
            # Truncate PM2.5 to one decimal place
            val = int(val * 10) / 10.0
            
            # Breakpoints for PM2.5
            breakpoints = [
                (0.0, 12.0, 0, 50),
                (12.1, 35.4, 51, 100),
                (35.5, 55.4, 101, 150),
                (55.5, 150.4, 151, 200),
                (150.5, 250.4, 201, 300),
                (250.5, 350.4, 301, 400),
                (350.5, 500.4, 401, 500)
            ]
            for bp_low, bp_high, i_low, i_high in breakpoints:
                if bp_low <= val <= bp_high:
                    aqi = ((i_high - i_low) / (bp_high - bp_low)) * (val - bp_low) + i_low
                    aqi_values.append(int(round(aqi)))
                    break
            else:
                if val > 500.4:
                    aqi_values.append(500)  # Cap at 500
        except ValueError:
            pass

    if pm10 is not None:
        try:
            val = float(pm10)
            # Truncate PM10 to integer
            val = int(val)
            
            # Breakpoints for PM10
            breakpoints = [
                (0, 54, 0, 50),
                (55, 154, 51, 100),
                (155, 254, 101, 150),
                (255, 354, 151, 200),
                (355, 424, 201, 300),
                (425, 504, 301, 400),
                (505, 604, 401, 500)
            ]
            for bp_low, bp_high, i_low, i_high in breakpoints:
                if bp_low <= val <= bp_high:
                    aqi = ((i_high - i_low) / (bp_high - bp_low)) * (val - bp_low) + i_low
                    aqi_values.append(int(round(aqi)))
                    break
            else:
                if val > 604:
                    aqi_values.append(500)  # Cap at 500
        except ValueError:
            pass
            
    if not aqi_values:
        return None
    return max(aqi_values)

def hopsworks_login():
    """
    Logs in to Hopsworks.
    On Windows, it specifies a temporary directory within the system temp for certs
    to avoid WinError 3 (/tmp not found) errors.
    """
    import sys
    import tempfile
    import hopsworks
    
    if sys.platform.startswith("win"):
        cert_dir = os.path.join(tempfile.gettempdir(), "hopsworks_certs")
        os.makedirs(cert_dir, exist_ok=True)
        return hopsworks.login(cert_folder=cert_dir)
    else:
        return hopsworks.login()

if __name__ == "__main__":
    print("Testing load_cities_config...")
    try:
        cities = load_cities_config()
        print(f"Loaded {len(cities)} cities successfully:")
        for city in cities:
            print(f" - {city['name']}: Lat {city['lat']}, Lon {city['lon']}")
    except Exception as e:
        print(f"Error loading cities config: {e}")

    print("\nTesting round_timestamp_to_hour...")
    t1 = "2026-07-30T16:45:00Z"
    t2 = 1782782400  # sample epoch
    print(f"String '{t1}' rounded to: {round_timestamp_to_hour(t1)}")
    print(f"Epoch {t2} rounded to: {round_timestamp_to_hour(t2)}")
    
    print("\nTesting compute_aqi_from_pollutants...")
    sample_pollutants = {"pm25": 12.0, "pm10": 54}
    print(f"AQI for PM2.5=12.0, PM10=54: {compute_aqi_from_pollutants(sample_pollutants)} (Expected: 50)")
    sample_pollutants_2 = {"pm25": 35.4}
    print(f"AQI for PM2.5=35.4: {compute_aqi_from_pollutants(sample_pollutants_2)} (Expected: 100)")
