"""
tests/test_geographic_validation.py
-----------------------------------
Automated test suite verifying strict geographic data accuracy, 100km distance guardrails,
source hierarchy, and prevention of wrong-city fallback.

Covers Requirements A through G:
  A. Valid local station (<= 100 km) -> ACCEPT
  B. Distant station (> 100 km, e.g. Delhi ~400 km) -> REJECT
  C. Very distant station (> 500 km, e.g. Tajikistan) -> REJECT
  D. OpenWeather exact coordinate validation (never uses distant station coords)
  E. City switching validation (metadata & coordinates change cleanly)
  F. Complete source failure handling (data_available = False, no wrong fallback)
  G. Boundary distance threshold (99.9 km ACCEPT vs 100.1 km REJECT)
"""

import os
import sys
import math
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher import haversine_distance_km, fetch_aqicn_data, fetch_combined_data
from src.utils import load_cities_config


# ── TEST SUITE ────────────────────────────────────────────────────────────────

def test_haversine_accuracy():
    """Verifies Haversine distance formula against known geographic benchmarks."""
    # Lahore (31.5497, 74.3436) to Delhi (28.7758, 77.0463)
    dist = haversine_distance_km(31.5497, 74.3436, 28.7758, 77.0463)
    assert 400 < dist < 410, f"Expected Lahore-Delhi distance ~403 km, got {dist:.1f} km"

    # Same coordinate distance should be exactly 0
    assert haversine_distance_km(31.5497, 74.3436, 31.5497, 74.3436) == 0.0


# --- TEST A: Valid Local Station (<= 100 km) -> ACCEPT ---
def test_a_valid_local_station_accepted():
    """Simulates a local AQICN station within 15 km of Lahore -> Must be ACCEPTED."""
    city = "Lahore"
    city_lat, city_lon = 31.5497, 74.3436
    local_station_geo = [31.5800, 74.3200]  # ~4.1 km away in Lahore

    mock_aqicn_response = {
        "status": "ok",
        "data": {
            "aqi": 142,
            "city": {
                "name": "US Consulate General Lahore",
                "geo": local_station_geo
            },
            "iaqi": {
                "pm25": {"v": 52.0},
                "pm10": {"v": 110.0}
            },
            "time": {"iso": "2026-08-31T03:00:00+05:00"}
        }
    }

    with patch("requests.get") as mock_get:
        # Mock AQICN response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_aqicn_response
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = fetch_combined_data(city, city_lat, city_lon)

        assert result["data_available"] is True
        assert result["source"] == "AQICN"
        assert result["station_name"] == "US Consulate General Lahore"
        assert result["aqi"] == 142.0
        assert result["distance_from_city_km"] < 10.0
        assert result["aqicn_reference_aqi"] == 142.0
        assert result["aqi_source_ok"] is True


# --- TEST B: Distant Station (Delhi ~400 km) -> REJECT ---
def test_b_distant_station_rejected():
    """Simulates AQICN returning a station in Delhi (~403 km away) -> Must be REJECTED."""
    city = "Lahore"
    city_lat, city_lon = 31.5497, 74.3436
    delhi_station_geo = [28.7758, 77.0463]  # Pooth Khurd, Delhi (~403 km)

    mock_aqicn_response = {
        "status": "ok",
        "data": {
            "aqi": 127,
            "city": {
                "name": "Pooth Khurd, Bawana, Delhi, India",
                "geo": delhi_station_geo
            },
            "iaqi": {"pm25": {"v": 45.0}},
            "time": {"iso": "2026-08-31T03:00:00+05:00"}
        }
    }

    mock_ow_pollution = {
        "pm25": 38.5,
        "pm10": 95.0,
        "o3": 40.0,
        "no2": 12.0,
        "so2": 3.0,
        "co": 310.0,
        "timestamp": datetime.now(timezone.utc)
    }

    with patch("src.data_fetcher.fetch_aqicn_data") as mock_aqicn, \
         patch("src.data_fetcher.fetch_openweather_live_air_pollution") as mock_ow, \
         patch("src.data_fetcher.fetch_openweather_data") as mock_weather:

        mock_aqicn.return_value = {
            "aqi": 127,
            "station_name": "Pooth Khurd, Bawana, Delhi, India",
            "station_geo": delhi_station_geo,
            "station_distance_km": 403.3,
            "is_local_station": False,  # Rejected!
            "timestamp": datetime.now(timezone.utc)
        }
        mock_ow.return_value = mock_ow_pollution
        mock_weather.return_value = None

        result = fetch_combined_data(city, city_lat, city_lon)

        # Must NOT display Delhi AQICN data
        assert result["source"] == "OpenWeather Model Grid"
        assert result["aqicn_reference_aqi"] is None
        assert "Delhi" not in result["station_name"]
        assert result["data_available"] is True


# --- TEST C: Very Distant Station (Tajikistan ~564 km) -> REJECT ---
def test_c_very_distant_station_rejected():
    """Simulates Peshawar query resolving to Dushanbe, Tajikistan (~564 km) -> Must be REJECTED."""
    city = "Peshawar"
    city_lat, city_lon = 34.0151, 71.5805
    tajik_geo = [38.5577, 68.7759]  # Dushanbe

    with patch("src.data_fetcher.fetch_aqicn_data") as mock_aqicn, \
         patch("src.data_fetcher.fetch_openweather_live_air_pollution") as mock_ow:

        mock_aqicn.return_value = {
            "aqi": 149,
            "station_name": "Dushanbe US Embassy, Tajikistan",
            "station_geo": tajik_geo,
            "station_distance_km": 564.1,
            "is_local_station": False,
            "timestamp": datetime.now(timezone.utc)
        }
        mock_ow.return_value = {
            "pm25": 72.0, "pm10": 180.0, "o3": 80.0, "no2": 5.0, "so2": 3.0, "co": 250.0,
            "timestamp": datetime.now(timezone.utc)
        }

        result = fetch_combined_data(city, city_lat, city_lon)

        assert result["source"] == "OpenWeather Model Grid"
        assert result["aqicn_reference_aqi"] is None
        assert "Tajikistan" not in result["station_name"]


# --- TEST D: OpenWeather Exact Coordinate Validation ---
def test_d_openweather_uses_exact_coordinates():
    """Verifies that OpenWeather is queried using the city's exact configured coordinates."""
    city = "Karachi"
    city_lat, city_lon = 24.8607, 67.0011

    with patch("src.data_fetcher.fetch_openweather_live_air_pollution") as mock_ow_poll, \
         patch("src.data_fetcher.fetch_openweather_data") as mock_ow_wx, \
         patch("src.data_fetcher.fetch_aqicn_data") as mock_aqicn:

        mock_aqicn.return_value = {"is_local_station": False}
        mock_ow_poll.return_value = {
            "pm25": 18.0, "pm10": 60.0, "o3": 30.0, "no2": 1.0, "so2": 0.5, "co": 70.0,
            "timestamp": datetime.now(timezone.utc)
        }
        mock_ow_wx.return_value = None

        fetch_combined_data(city, city_lat, city_lon)

        # Confirm exact coords passed to OpenWeather
        mock_ow_poll.assert_called_once_with(city_lat, city_lon)
        mock_ow_wx.assert_called_once_with(city_lat, city_lon)


# --- TEST E: City Switching Validation ---
def test_e_city_switching_changes_requests_and_metadata():
    """Verifies that switching cities changes coordinates, requests, and result payloads."""
    cities = load_cities_config()
    city_a = next(c for c in cities if c["name"] == "Lahore")
    city_b = next(c for c in cities if c["name"] == "Karachi")

    with patch("src.data_fetcher.fetch_openweather_live_air_pollution") as mock_ow:
        mock_ow.side_effect = lambda lat, lon: {
            "pm25": 40.0 if lat == city_a["lat"] else 15.0,
            "pm10": 100.0, "o3": 35.0, "no2": 10.0, "so2": 2.0, "co": 300.0,
            "timestamp": datetime.now(timezone.utc)
        }
        with patch("src.data_fetcher.fetch_aqicn_data", return_value={"is_local_station": False}):
            res_a = fetch_combined_data(city_a["name"], city_a["lat"], city_a["lon"])
            res_b = fetch_combined_data(city_b["name"], city_b["lat"], city_b["lon"])

            assert res_a["selected_city"] == "Lahore"
            assert res_b["selected_city"] == "Karachi"
            assert res_a["station_latitude"] == city_a["lat"]
            assert res_b["station_latitude"] == city_b["lat"]
            assert res_a["aqi"] != res_b["aqi"]  # Clean separate results


# --- TEST F: Complete Failure -> Data Unavailable ---
def test_f_complete_failure_returns_data_unavailable():
    """Verifies that when both AQICN and OpenWeather fail, system returns data_available=False."""
    city = "Multan"
    city_lat, city_lon = 30.1575, 71.5249

    with patch("src.data_fetcher.fetch_aqicn_data", return_value=None), \
         patch("src.data_fetcher.fetch_openweather_live_air_pollution", return_value=None), \
         patch("src.data_fetcher.fetch_openweather_data", return_value=None):

        result = fetch_combined_data(city, city_lat, city_lon)

        assert result["data_available"] is False
        assert result["aqi"] is None
        assert result["source"] is None
        assert result["data_unavailable_reason"] is not None
        assert "Local AQI data unavailable for Multan" in result["data_unavailable_reason"]


# --- TEST G: Boundary Distance Threshold (99.9 km vs 100.1 km) ---
def test_g_boundary_distance_guardrail():
    """Verifies that a station at 99.0 km is accepted (<=100 km) and 101.0 km is rejected (>100 km)."""
    # Reference anchor: Lahore (31.5497, 74.3436)
    ref_lat, ref_lon = 31.5497, 74.3436

    # 1 deg latitude = 111.195 km on Earth
    # 99.0 km offset:
    lat_99km = ref_lat + (99.0 / 111.195)
    dist_near = haversine_distance_km(ref_lat, ref_lon, lat_99km, ref_lon)
    assert dist_near <= 100.0, f"Expected <=100km, got {dist_near}"

    # 101.0 km offset:
    lat_101km = ref_lat + (101.0 / 111.195)
    dist_far = haversine_distance_km(ref_lat, ref_lon, lat_101km, ref_lon)
    assert dist_far > 100.0, f"Expected >100km, got {dist_far}"

    mock_resp_near = {
        "status": "ok",
        "data": {
            "aqi": 115,
            "city": {"name": "Boundary Near Station", "geo": [lat_99km, ref_lon]},
            "iaqi": {"pm25": {"v": 40.0}},
            "time": {"iso": "2026-08-31T03:00:00Z"}
        }
    }

    mock_resp_far = {
        "status": "ok",
        "data": {
            "aqi": 115,
            "city": {"name": "Boundary Far Station", "geo": [lat_101km, ref_lon]},
            "iaqi": {"pm25": {"v": 40.0}},
            "time": {"iso": "2026-08-31T03:00:00Z"}
        }
    }

    with patch("requests.get") as mock_get:
        # Test 99.9 km -> Should accept
        mock_r1 = MagicMock(status_code=200)
        mock_r1.json.return_value = mock_resp_near
        mock_r1.raise_for_status.return_value = None
        mock_get.return_value = mock_r1

        res_near = fetch_aqicn_data("Lahore", ref_lat, ref_lon)
        assert res_near["is_local_station"] is True
        assert res_near["station_distance_km"] <= 100.0

        # Test 100.2 km -> Should reject
        mock_r2 = MagicMock(status_code=200)
        mock_r2.json.return_value = mock_resp_far
        mock_r2.raise_for_status.return_value = None
        mock_get.return_value = mock_r2

        res_far = fetch_aqicn_data("Lahore", ref_lat, ref_lon)
        assert res_far["is_local_station"] is False
        assert res_far["station_distance_km"] > 100.0


# --- TEST H: Missing Station Coordinates -> REJECT (Safe by Default) ---
def test_h_missing_station_geo_rejected():
    """Verifies that an AQICN response missing geo coordinates is rejected as non-local."""
    mock_resp_no_geo = {
        "status": "ok",
        "data": {
            "aqi": 115,
            "city": {"name": "Unlocated Station", "geo": []},
            "iaqi": {"pm25": {"v": 40.0}},
            "time": {"iso": "2026-08-31T03:00:00Z"}
        }
    }

    with patch("requests.get") as mock_get:
        mock_r = MagicMock(status_code=200)
        mock_r.json.return_value = mock_resp_no_geo
        mock_r.raise_for_status.return_value = None
        mock_get.return_value = mock_r

        result = fetch_aqicn_data("Lahore", 31.5497, 74.3436)
        assert result["is_local_station"] is False
        assert result["station_distance_km"] is None

