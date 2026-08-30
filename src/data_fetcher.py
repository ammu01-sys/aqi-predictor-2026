import os
import requests
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

AQICN_API_KEY = os.getenv("AQICN_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

logger = logging.getLogger(__name__)

def fetch_aqicn_data(city, lat, lon):
    """
    Fetches AQI & pollutant data from AQICN API for a given city and coordinates.
    Returns:
        dict: A dictionary containing pm25, pm10, o3, no2, so2, co, aqi, and timestamp.
              Returns None if the fetch fails.
    """
    if not AQICN_API_KEY:
        logger.error("AQICN_API_KEY is not set.")
        return None
        
    # AQICN geo-localized feed endpoint
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={AQICN_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "ok":
            logger.error(f"AQICN API error for {city}: {data.get('data')}")
            return None
            
        res_data = data.get("data", {})
        iaqi = res_data.get("iaqi", {})
        time_data = res_data.get("time", {})
        
        # CRITICAL TIMEZONE CONVERSION FOR AQICN:
        # AQICN's API returns observation timestamps in the station's LOCAL timezone.
        # - 'time.iso' provides an ISO string with the local timezone offset (e.g., '2026-08-28T05:00:00+05:00').
        # - 'time.s' and 'time.tz' provide local time string and offset (e.g., '2026-08-28 05:00:00' and '+05:00').
        # We parse the local timestamp WITH its offset and convert it to true UTC (+00:00).
        timestamp = None
        iso_str = time_data.get("iso")
        time_s = time_data.get("s")
        time_tz = time_data.get("tz")
        
        if iso_str:
            try:
                import pandas as pd
                timestamp = pd.to_datetime(iso_str, utc=True).to_pydatetime()
            except Exception:
                try:
                    dt = datetime.fromisoformat(iso_str)
                    timestamp = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pass
                    
        if not timestamp and time_s and time_tz:
            try:
                combined_iso = f"{time_s.replace(' ', 'T')}{time_tz}"
                import pandas as pd
                timestamp = pd.to_datetime(combined_iso, utc=True).to_pydatetime()
            except Exception:
                pass
                
        if not timestamp:
            # Fallback to current UTC time if timestamp parsing fails
            timestamp = datetime.now(timezone.utc)
            
        pollutants = {
            "pm25": iaqi.get("pm25", {}).get("v"),
            "pm10": iaqi.get("pm10", {}).get("v"),
            "o3": iaqi.get("o3", {}).get("v"),
            "no2": iaqi.get("no2", {}).get("v"),
            "so2": iaqi.get("so2", {}).get("v"),
            "co": iaqi.get("co", {}).get("v"),
            "aqi": res_data.get("aqi"),
            "timestamp": timestamp
        }
        return pollutants
    except requests.exceptions.RequestException as e:
        logger.error(f"AQICN API request failed for {city}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing AQICN API data for {city}: {e}")
        return None

def fetch_openweather_live_air_pollution(lat, lon):
    """
    Fetches current-hour pollutant concentrations (PM2.5, PM10, O3, NO2, SO2, CO)
    from OpenWeather's free-tier live Air Pollution API (/data/2.5/air_pollution).
    Returns a dict of pollutant fields, or None on failure.

    NOTE: This endpoint is available on the free tier and returns the same pollutant
    concentration units (µg/m³) as the historical endpoint used in backfill.py,
    making live and historical AQI values directly comparable.
    """
    if not OPENWEATHER_API_KEY:
        logger.error("OPENWEATHER_API_KEY is not set.")
        return None

    url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = data.get("list", [])
        if not items:
            logger.warning(f"No items in OW live air pollution response for ({lat}, {lon}).")
            return None

        item = items[0]  # Most recent measurement
        comp = item.get("components", {})
        dt = item.get("dt")
        timestamp = datetime.fromtimestamp(dt, tz=timezone.utc) if dt else datetime.now(timezone.utc)

        return {
            "pm25": comp.get("pm2_5"),
            "pm10": comp.get("pm10"),
            "o3": comp.get("o3"),
            "no2": comp.get("no2"),
            "so2": comp.get("so2"),
            "co": comp.get("co"),
            "timestamp": timestamp,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"OW live air pollution request failed for ({lat}, {lon}): {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing OW live air pollution data for ({lat}, {lon}): {e}")
        return None


def fetch_openweather_data(lat, lon):
    """
    Fetches temperature, humidity, wind speed, and pressure from OpenWeather API.
    Returns:
        dict: A dictionary containing temperature, humidity, wind_speed, pressure, and timestamp.
              Returns None if the fetch fails.
    """
    if not OPENWEATHER_API_KEY:
        logger.error("OPENWEATHER_API_KEY is not set.")
        return None
        
    # OpenWeather Current Weather endpoint
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        main = data.get("main", {})
        wind = data.get("wind", {})
        
        # OPENWEATHER TIMEZONE HANDLING:
        # OpenWeather returns 'dt' as standard UTC Unix epoch seconds (seconds since 1970-01-01 00:00:00 UTC).
        # datetime.fromtimestamp(dt, tz=timezone.utc) correctly produces a timezone-aware true UTC datetime.
        dt = data.get("dt")
        if dt:
            timestamp = datetime.fromtimestamp(dt, tz=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
            
        weather = {
            "temperature": main.get("temp"),
            "humidity": main.get("humidity"),
            "wind_speed": wind.get("speed"),
            "pressure": main.get("pressure"),
            "timestamp": timestamp
        }
        return weather
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenWeather API request failed for coords ({lat}, {lon}): {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing OpenWeather API data: {e}")
        return None

def fetch_combined_data(city, lat, lon):
    """
    Fetches and merges data from AQICN and OpenWeather for a given city.

    AQI CONSISTENCY DESIGN (see docs/decisions.md §8):
    - The primary `aqi` field is computed from OpenWeather's live pollutant concentrations
      via compute_aqi_from_pollutants() (US EPA piecewise linear formula), matching the
      method used in historical backfill (backfill.py). This ensures live and historical
      AQI values are on an identical, internally consistent scale for model training/inference.
    - AQICN's native station AQI is stored separately as `aqicn_reference_aqi` for
      dashboard display and monitoring only. It is NOT a model feature or training target.
    - OpenWeather's live /air_pollution endpoint provides pollutant concentrations (µg/m³)
      identical in units to the historical endpoint, ensuring source consistency.
    - Fallback: if OpenWeather's live air pollution call fails, AQICN's pollutant
      concentrations are used to compute AQI via the same EPA formula.
    """
    # Import inside function to avoid circular imports
    from src.utils import round_timestamp_to_hour, compute_aqi_from_pollutants

    aqi_data = fetch_aqicn_data(city, lat, lon)
    ow_pollution_data = fetch_openweather_live_air_pollution(lat, lon)
    weather_data = fetch_openweather_data(lat, lon)

    # Initialize combined dictionary
    combined = {
        "city": city,
        "timestamp": None,
        # Pollutant concentrations (from OpenWeather live, or AQICN fallback)
        "pm25": None,
        "pm10": None,
        "o3": None,
        "no2": None,
        "so2": None,
        "co": None,
        # Primary AQI: EPA formula applied to OpenWeather pollutants (consistent with backfill)
        "aqi": None,
        # Reference-only: AQICN's native station AQI for display/comparison (not modeled)
        "aqicn_reference_aqi": None,
        # Weather
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "pressure": None,
        # Source flags
        "aqi_source_ok": False,
        "weather_source_ok": False,
    }

    ow_ts = None
    aqi_ts = None
    weather_ts = None

    # --- Primary pollutant source: OpenWeather live air pollution ---
    if ow_pollution_data:
        try:
            ow_ts = round_timestamp_to_hour(ow_pollution_data["timestamp"])
            combined["pm25"] = ow_pollution_data["pm25"]
            combined["pm10"] = ow_pollution_data["pm10"]
            combined["o3"] = ow_pollution_data["o3"]
            combined["no2"] = ow_pollution_data["no2"]
            combined["so2"] = ow_pollution_data["so2"]
            combined["co"] = ow_pollution_data["co"]
            computed_aqi = compute_aqi_from_pollutants(combined)
            if computed_aqi is not None:
                combined["aqi"] = computed_aqi
                combined["aqi_source_ok"] = True
                logger.debug(f"[{city}] AQI computed from OW live pollutants: {computed_aqi}")
        except Exception as e:
            logger.error(f"Error merging OW live air pollution data for {city}: {e}")

    # --- AQICN: store native AQI as reference; use as pollutant fallback if OW failed ---
    if aqi_data:
        try:
            aqi_ts = round_timestamp_to_hour(aqi_data["timestamp"])
            # Always capture AQICN's native AQI for display reference
            native_aqi = aqi_data.get("aqi")
            if native_aqi is not None and native_aqi != "-":
                combined["aqicn_reference_aqi"] = native_aqi

            # Fallback: if OW live air pollution failed, use AQICN pollutants
            if not combined["aqi_source_ok"]:
                logger.warning(f"[{city}] OW live air pollution failed. Falling back to AQICN pollutants.")
                combined["pm25"] = aqi_data["pm25"]
                combined["pm10"] = aqi_data["pm10"]
                combined["o3"] = aqi_data["o3"]
                combined["no2"] = aqi_data["no2"]
                combined["so2"] = aqi_data["so2"]
                combined["co"] = aqi_data["co"]
                computed_aqi = compute_aqi_from_pollutants(combined)
                if computed_aqi is not None:
                    combined["aqi"] = computed_aqi
                    combined["aqi_source_ok"] = True
                    logger.debug(f"[{city}] AQI computed from AQICN fallback pollutants: {computed_aqi}")
        except Exception as e:
            logger.error(f"Error merging AQICN data for {city}: {e}")

    # --- Weather: temperature, humidity, wind speed, pressure ---
    if weather_data:
        try:
            weather_ts = round_timestamp_to_hour(weather_data["timestamp"])
            combined["temperature"] = weather_data["temperature"]
            combined["humidity"] = weather_data["humidity"]
            combined["wind_speed"] = weather_data["wind_speed"]
            combined["pressure"] = weather_data["pressure"]
            combined["weather_source_ok"] = True
        except Exception as e:
            logger.error(f"Error merging OpenWeather weather data for {city}: {e}")
            combined["weather_source_ok"] = False

    # Resolve final aligned timestamp: prefer OW pollution ts, then AQICN ts, then weather ts
    if ow_ts:
        combined["timestamp"] = ow_ts
    elif aqi_ts:
        combined["timestamp"] = aqi_ts
    elif weather_ts:
        combined["timestamp"] = weather_ts
    else:
        combined["timestamp"] = round_timestamp_to_hour(datetime.now(timezone.utc))

    return combined

if __name__ == "__main__":
    import sys
    # Add project root to path if running directly
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.utils import load_cities_config
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    print("==================================================")
    print("STEP 1: Testing fetch_combined_data for all configured cities")
    print("==================================================")
    try:
        cities = load_cities_config()
    except Exception as e:
        print(f"Failed to load config: {e}")
        cities = []
        
    for city_info in cities:
        name = city_info["name"]
        lat = city_info["lat"]
        lon = city_info["lon"]
        print(f"\n--- Fetching data for {name} ({lat}, {lon}) ---")
        
        # Test individual fetches
        aqi_raw = fetch_aqicn_data(name, lat, lon)
        weather_raw = fetch_openweather_data(lat, lon)
        combined = fetch_combined_data(name, lat, lon)
        
        print(f"AQICN raw success: {aqi_raw is not None}")
        print(f"OpenWeather raw success: {weather_raw is not None}")
        print(f"Combined Result: {combined}")
        
    print("\n==================================================")
    print("STEP 2: Testing API key failure fallback logic")
    print("==================================================")
    # Temporarily break OpenWeather key
    original_ow_key = OPENWEATHER_API_KEY
    globals()["OPENWEATHER_API_KEY"] = "INVALID_KEY_TEST"
    
    print("Simulating invalid OpenWeather API key for Lahore...")
    lh = cities[0] if cities else {"name": "Lahore", "lat": 31.5497, "lon": 74.3436}
    combined_fallback = fetch_combined_data(lh["name"], lh["lat"], lh["lon"])
    print(f"Combined Result (OpenWeather broken):")
    print(f" - weather_source_ok: {combined_fallback['weather_source_ok']} (Expected: False)")
    print(f" - aqi_source_ok: {combined_fallback['aqi_source_ok']}")
    print(f" - temperature: {combined_fallback['temperature']} (Expected: None)")
    print(f" - aqi: {combined_fallback['aqi']}")
    
    # Restore key
    globals()["OPENWEATHER_API_KEY"] = original_ow_key
    
    print("\n==================================================")
    print("STEP 3: Testing loop resilience with invalid coordinates for one city")
    print("==================================================")
    # Modify the second city's coordinates to be invalid
    test_cities = [c.copy() for c in cities]
    if len(test_cities) > 1:
        test_cities[1]["lat"] = 999.0  # Invalid latitude
        test_cities[1]["lon"] = 999.0  # Invalid longitude
        test_cities[1]["name"] = test_cities[1]["name"] + " (INVALID COORDS TEST)"
        
    print(f"Starting loop over {len(test_cities)} cities (second city has invalid coordinates)...")
    for city_info in test_cities:
        name = city_info["name"]
        lat = city_info["lat"]
        lon = city_info["lon"]
        try:
            print(f"\nProcessing {name}...")
            combined = fetch_combined_data(name, lat, lon)
            print(f"Result for {name}: aqi_source_ok={combined['aqi_source_ok']}, weather_source_ok={combined['weather_source_ok']}")
        except Exception as e:
            print(f"CRITICAL ERROR: Loop crashed on city {name}: {e}")
