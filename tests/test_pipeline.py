"""
Lightweight sanity tests for the AQI prediction pipeline.
Run locally with: pytest tests/test_pipeline.py -v

These tests are intentionally offline — they do NOT call any external APIs
or connect to Hopsworks. They validate pure logic, data contracts, and
schema correctness using synthetic inputs.
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
# 1. utils.py — EPA AQI formula
# ─────────────────────────────────────────────

class TestComputeAqiFromPollutants:
    """Validate the US EPA piecewise linear AQI formula."""

    from src.utils import compute_aqi_from_pollutants

    def test_good_air_returns_low_aqi(self):
        from src.utils import compute_aqi_from_pollutants
        result = compute_aqi_from_pollutants({"pm25": 5.0, "pm10": 20.0})
        assert result is not None
        assert 0 <= result <= 50, f"Expected Good AQI (0-50), got {result}"

    def test_unhealthy_pm25_returns_high_aqi(self):
        from src.utils import compute_aqi_from_pollutants
        # PM2.5 = 55.5 µg/m³ is in Unhealthy range (AQI 151–200)
        result = compute_aqi_from_pollutants({"pm25": 55.5})
        assert result is not None
        assert 151 <= result <= 200, f"Expected Unhealthy AQI (151-200), got {result}"

    def test_none_pollutants_returns_none(self):
        from src.utils import compute_aqi_from_pollutants
        result = compute_aqi_from_pollutants({"pm25": None, "pm10": None})
        assert result is None

    def test_empty_dict_returns_none(self):
        from src.utils import compute_aqi_from_pollutants
        result = compute_aqi_from_pollutants({})
        assert result is None


# ─────────────────────────────────────────────
# 2. data_fetcher.py — fetch_combined_data output contract
# ─────────────────────────────────────────────

class TestFetchCombinedDataContract:
    """Verify output dictionary keys and types without hitting any real API."""

    REQUIRED_KEYS = [
        "city", "timestamp", "aqi", "aqicn_reference_aqi",
        "pm25", "pm10", "o3", "no2", "so2", "co",
        "temperature", "humidity", "wind_speed", "pressure",
        "aqi_source_ok", "weather_source_ok",
    ]

    def _make_mock_ow_pollution(self):
        from datetime import datetime, timezone
        return {
            "pm25": 45.0, "pm10": 60.0, "o3": 80.0,
            "no2": 30.0, "so2": 10.0, "co": 500.0,
            "timestamp": datetime.now(timezone.utc),
        }

    def _make_mock_aqicn(self):
        from datetime import datetime, timezone
        return {
            "pm25": 44.0, "pm10": 58.0, "o3": 79.0,
            "no2": 29.0, "so2": 9.0, "co": 490.0,
            "aqi": 130,
            "timestamp": datetime.now(timezone.utc),
        }

    def _make_mock_weather(self):
        from datetime import datetime, timezone
        return {
            "temperature": 32.0, "humidity": 60.0,
            "wind_speed": 3.5, "pressure": 1010.0,
            "timestamp": datetime.now(timezone.utc),
        }

    def test_all_sources_ok_returns_required_keys(self):
        from src.data_fetcher import fetch_combined_data
        with patch("src.data_fetcher.fetch_openweather_live_air_pollution", return_value=self._make_mock_ow_pollution()), \
             patch("src.data_fetcher.fetch_aqicn_data", return_value=self._make_mock_aqicn()), \
             patch("src.data_fetcher.fetch_openweather_data", return_value=self._make_mock_weather()):
            result = fetch_combined_data("Lahore", 31.5497, 74.3436)
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_primary_aqi_is_epa_formula_not_aqicn(self):
        """Primary aqi must be computed from OW pollutants, not AQICN's native value."""
        from src.data_fetcher import fetch_combined_data
        aqicn_native = 999  # Deliberately wrong to detect if it leaks into aqi
        mock_aqicn = self._make_mock_aqicn()
        mock_aqicn["aqi"] = aqicn_native
        with patch("src.data_fetcher.fetch_openweather_live_air_pollution", return_value=self._make_mock_ow_pollution()), \
             patch("src.data_fetcher.fetch_aqicn_data", return_value=mock_aqicn), \
             patch("src.data_fetcher.fetch_openweather_data", return_value=self._make_mock_weather()):
            result = fetch_combined_data("Lahore", 31.5497, 74.3436)
        assert result["aqi"] != aqicn_native, "Primary aqi must NOT be AQICN's native value"
        assert result["aqicn_reference_aqi"] == aqicn_native, "AQICN native must be stored in aqicn_reference_aqi"

    def test_ow_pollution_failure_falls_back_to_aqicn(self):
        """If OW live air pollution fails, AQICN pollutants must be used as fallback."""
        from src.data_fetcher import fetch_combined_data
        with patch("src.data_fetcher.fetch_openweather_live_air_pollution", return_value=None), \
             patch("src.data_fetcher.fetch_aqicn_data", return_value=self._make_mock_aqicn()), \
             patch("src.data_fetcher.fetch_openweather_data", return_value=self._make_mock_weather()):
            result = fetch_combined_data("Lahore", 31.5497, 74.3436)
        assert result["aqi_source_ok"] is True, "Should fallback to AQICN pollutants successfully"
        assert result["aqi"] is not None, "aqi must be computed from AQICN fallback"

    def test_both_aqi_sources_fail_gracefully(self):
        """If both OW and AQICN fail, result must still have all keys."""
        from src.data_fetcher import fetch_combined_data
        with patch("src.data_fetcher.fetch_openweather_live_air_pollution", return_value=None), \
             patch("src.data_fetcher.fetch_aqicn_data", return_value=None), \
             patch("src.data_fetcher.fetch_openweather_data", return_value=None):
            result = fetch_combined_data("Lahore", 31.5497, 74.3436)
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key after total failure: {key}"
        assert result["aqi_source_ok"] is False
        assert result["weather_source_ok"] is False


# ─────────────────────────────────────────────
# 3. feature_engineering.py — column contract
# ─────────────────────────────────────────────

class TestFeatureEngineering:
    """Verify engineer_all_features() produces expected columns."""

    EXPECTED_COLS = [
        "aqi_lag_1h", "aqi_lag_3h", "aqi_lag_6h", "aqi_lag_24h",
        "aqi_rolling_mean_6h", "aqi_rolling_std_6h",
        "aqi_rolling_mean_24h", "aqi_rolling_std_24h",
        "aqi_change_rate",
        "hour", "day_of_week", "day_of_month", "month", "is_weekend",
    ]

    def _make_minimal_df(self, n=30):
        from datetime import datetime, timezone, timedelta
        base = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
        rows = []
        for i in range(n):
            rows.append({
                "city": "Lahore",
                "timestamp": base + timedelta(hours=i),
                "aqi": float(100 + i),
                "pm25": 40.0, "pm10": 60.0, "o3": 30.0,
                "no2": 20.0, "so2": 5.0, "co": 400.0,
                "temperature": None, "humidity": None,
                "wind_speed": None, "pressure": None,
                "aqi_source_ok": True, "weather_source_ok": False,
                "aqicn_reference_aqi": None,
            })
        return pd.DataFrame(rows)

    def test_all_expected_columns_present(self):
        from src.feature_engineering import engineer_all_features
        df = self._make_minimal_df(30)
        result = engineer_all_features(df)
        for col in self.EXPECTED_COLS:
            assert col in result.columns, f"Missing column: {col}"

    def test_city_onehot_column_present(self):
        from src.feature_engineering import engineer_all_features
        df = self._make_minimal_df(30)
        result = engineer_all_features(df)
        city_cols = [c for c in result.columns if c.startswith("city_")]
        assert len(city_cols) >= 1, "No city one-hot columns found"

    def test_no_future_leakage_in_lags(self):
        """
        Lag features must only reference past values — never future rows.
        Cold-start design (decisions.md §1): when no past row exists, lag is
        filled with current AQI (persistence fallback), not left as NaN.
        This test validates the lag ordering: row[i].aqi_lag_1h == row[i-1].aqi
        """
        from src.feature_engineering import engineer_all_features
        df = self._make_minimal_df(30)
        result = engineer_all_features(df)
        # Row 0: cold-start — lag_1h is filled with its own AQI (persistence fallback)
        assert result["aqi_lag_1h"].iloc[0] == result["aqi"].iloc[0], \
            "Row 0 lag_1h should equal its own AQI (cold-start persistence fallback)"
        # Row 1: lag_1h must equal row 0's AQI (correct chronological lag)
        expected = result["aqi"].iloc[0]
        actual = result["aqi_lag_1h"].iloc[1]
        assert abs(actual - expected) < 0.01, \
            f"Row 1 aqi_lag_1h should equal row 0's AQI ({expected}), got {actual}"
        # Row 5: lag_1h must equal row 4's AQI (not row 6 — no forward leakage)
        assert abs(result["aqi_lag_1h"].iloc[5] - result["aqi"].iloc[4]) < 0.01, \
            "aqi_lag_1h must reference the immediately preceding row, not a future row"


# ─────────────────────────────────────────────
# 4. feature_pipeline.py — schema cast
# ─────────────────────────────────────────────

class TestCastDataframeSchema:
    """Verify cast_dataframe_schema() types float/int/bool columns correctly."""

    def _make_raw_df(self):
        from datetime import datetime, timezone
        return pd.DataFrame([{
            "city": "Karachi",
            "timestamp": datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
            "aqi": "150",           # String — should be cast to float
            "aqicn_reference_aqi": "145",
            "pm25": "42.5",
            "pm10": None,
            "o3": "80", "no2": "30", "so2": "10", "co": "500",
            "temperature": None, "humidity": None,
            "wind_speed": None, "pressure": None,
            "hour": "14", "day_of_week": "2", "day_of_month": "1",
            "month": "8", "is_weekend": "0",
            "aqi_source_ok": True, "weather_source_ok": False,
            "target_24h": "155.0", "target_48h": "160.0", "target_72h": "158.0",
            "aqi_lag_1h": "149.0", "aqi_lag_3h": "147.0",
            "aqi_lag_6h": "145.0", "aqi_lag_24h": "130.0",
            "aqi_rolling_mean_6h": "146.0", "aqi_rolling_std_6h": "3.0",
            "aqi_rolling_mean_24h": "140.0", "aqi_rolling_std_24h": "8.0",
            "aqi_change_rate": "1.0",
            "city_karachi": "1", "city_lahore": "0",
        }])

    def test_aqi_cast_to_float(self):
        from src.feature_pipeline import cast_dataframe_schema
        df = cast_dataframe_schema(self._make_raw_df())
        assert df["aqi"].dtype == float
        assert df["aqi"].iloc[0] == 150.0

    def test_aqicn_reference_aqi_cast_to_float(self):
        from src.feature_pipeline import cast_dataframe_schema
        df = cast_dataframe_schema(self._make_raw_df())
        assert df["aqicn_reference_aqi"].dtype == float
        assert df["aqicn_reference_aqi"].iloc[0] == 145.0

    def test_hour_cast_to_int(self):
        from src.feature_pipeline import cast_dataframe_schema
        df = cast_dataframe_schema(self._make_raw_df())
        assert df["hour"].dtype in [int, np.int64, np.int32]
        assert df["hour"].iloc[0] == 14

    def test_timestamp_is_utc(self):
        from src.feature_pipeline import cast_dataframe_schema
        df = cast_dataframe_schema(self._make_raw_df())
        assert df["timestamp"].dt.tz is not None, "timestamp must be timezone-aware"
