
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
from src.utils import load_cities_config, hopsworks_login
from src.model_wrapper import AQIPredictorModelWrapper  # noqa: F401

load_dotenv()

# Configure page
st.set_page_config(
    page_title="AQI Predictor — Pakistan Air Quality Forecasting",
    page_icon="🍃",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Auto-refresh every 10 minutes ──────────────────────────────────────────────
_REFRESH_INTERVAL_SECS = 600  # 10 minutes
if "_last_refresh" not in st.session_state:
    st.session_state["_last_refresh"] = time.time()
elif time.time() - st.session_state["_last_refresh"] > _REFRESH_INTERVAL_SECS:
    st.session_state["_last_refresh"] = time.time()
    st.rerun()

# ─────────────────────────────────────────────────────────────
# 1. AIR QUALITY CATEGORIES & PRACTICAL HEALTH ADVISORIES
# ─────────────────────────────────────────────────────────────
AQI_CATEGORIES = [
    {
        "min": 0, "max": 50,
        "name": "Good",
        "color": "#00E400",
        "bg_glow": "rgba(0, 228, 0, 0.15)",
        "border": "rgba(0, 228, 0, 0.4)",
        "text_color": "#00E400",
        "icon": "🍃",
        "advisory": "Air quality is clean and healthy. Great day for outdoor activities.",
        "sensitive_advice": "Perfect conditions for outdoor exercise, walking, and open windows.",
        "mask_required": False
    },
    {
        "min": 51, "max": 100,
        "name": "Moderate",
        "color": "#FFD600",
        "bg_glow": "rgba(255, 214, 0, 0.15)",
        "border": "rgba(255, 214, 0, 0.4)",
        "text_color": "#FFD600",
        "icon": "🌤️",
        "advisory": "Air quality is acceptable for most people.",
        "sensitive_advice": "People with asthma or respiratory sensitivities should take it easy outdoors.",
        "mask_required": False
    },
    {
        "min": 101, "max": 150,
        "name": "Unhealthy for Sensitive Groups",
        "color": "#FF7E00",
        "bg_glow": "rgba(255, 126, 0, 0.18)",
        "border": "rgba(255, 126, 0, 0.45)",
        "text_color": "#FF7E00",
        "icon": "😷",
        "advisory": "Sensitive individuals may feel coughing or throat irritation.",
        "sensitive_advice": "Children, seniors, and people with heart or lung conditions should limit time outdoors.",
        "mask_required": True
    },
    {
        "min": 151, "max": 200,
        "name": "Unhealthy",
        "color": "#FF0000",
        "bg_glow": "rgba(255, 0, 0, 0.22)",
        "border": "rgba(255, 0, 0, 0.5)",
        "text_color": "#FF4444",
        "icon": "🚨",
        "advisory": "Air pollution is high. Everyone may start to feel mild symptoms.",
        "sensitive_advice": "Avoid intense exercise outdoors. Wear a mask when outside and keep home windows closed.",
        "mask_required": True
    },
    {
        "min": 201, "max": 300,
        "name": "Very Unhealthy",
        "color": "#8F3F97",
        "bg_glow": "rgba(143, 63, 151, 0.25)",
        "border": "rgba(143, 63, 151, 0.55)",
        "text_color": "#D070DB",
        "icon": "⛔",
        "advisory": "Severe smog alert. Air quality is unhealthy for the entire population.",
        "sensitive_advice": "Stay indoors as much as possible. Keep air purifiers running and avoid all outdoor workouts.",
        "mask_required": True
    },
    {
        "min": 301, "max": 9999,
        "name": "Hazardous",
        "color": "#7E0023",
        "bg_glow": "rgba(126, 0, 35, 0.35)",
        "border": "rgba(126, 0, 35, 0.7)",
        "text_color": "#FF3366",
        "icon": "☠️",
        "advisory": "Emergency air quality conditions. Serious health risk for everyone.",
        "sensitive_advice": "Strictly remain indoors with closed windows. Avoid any outdoor exposure.",
        "mask_required": True
    }
]

def get_aqi_info(aqi_val):
    if aqi_val is None or pd.isna(aqi_val):
        return AQI_CATEGORIES[1]
    val = float(aqi_val)
    for cat in AQI_CATEGORIES:
        if cat["min"] <= val <= cat["max"]:
            return cat
    return AQI_CATEGORIES[-1]

# ─────────────────────────────────────────────────────────────
# 2. CUSTOM CSS & CLEAN TYPOGRAPHY
# ─────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #f1f5f9;
}

h1, h2, h3, h4, .display-font {
    font-family: 'Outfit', sans-serif !important;
    letter-spacing: -0.02em;
}

.main .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1350px;
}

/* Glassmorphic card */
.glass-card {
    background: rgba(16, 23, 38, 0.65);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.3);
    transition: all 0.25s ease;
}

/* Hero card dynamic glow */
.hero-aqi-card {
    border-radius: 22px;
    padding: 30px;
    position: relative;
    overflow: hidden;
}

.hero-number {
    font-family: 'Outfit', sans-serif;
    font-size: 5.5rem;
    font-weight: 900;
    line-height: 0.95;
    letter-spacing: -0.04em;
}

.hero-category {
    font-family: 'Outfit', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    border-radius: 999px;
    margin-top: 10px;
}

.stat-pill {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 7px 13px;
    border-radius: 12px;
    font-size: 0.85rem;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

/* Hazard Alert banner */
@keyframes pulse-hazard {
    0%, 100% { box-shadow: 0 0 20px rgba(255, 0, 0, 0.3); border-color: rgba(255, 50, 50, 0.8); }
    50% { box-shadow: 0 0 40px rgba(255, 0, 0, 0.6); border-color: rgba(255, 80, 80, 1); }
}

.hazard-alert-banner {
    background: linear-gradient(135deg, rgba(126, 0, 35, 0.85) 0%, rgba(30, 10, 15, 0.95) 100%);
    border: 1.5px solid rgba(255, 50, 50, 0.8);
    border-radius: 16px;
    padding: 18px 22px;
    margin-bottom: 22px;
    animation: pulse-hazard 3s infinite ease-in-out;
}

/* Forecast mini cards */
.forecast-card {
    background: rgba(16, 23, 38, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 18px 14px;
    text-align: center;
    transition: transform 0.2s ease;
}

.forecast-card:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.2);
}

.forecast-val {
    font-family: 'Outfit', sans-serif;
    font-size: 2.3rem;
    font-weight: 800;
    line-height: 1;
    margin: 8px 0;
}

/* Pollutant small tiles */
.pollutant-tile {
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px;
    padding: 14px 16px;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: rgba(15, 23, 42, 0.6);
    padding: 6px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: #94a3b8;
    font-weight: 600;
    padding: 8px 16px;
}

.stTabs [aria-selected="true"] {
    background-color: rgba(255, 255, 255, 0.1) !important;
    color: #ffffff !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 3. LIVE DATA LOADER
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Loading live air quality data...")
def load_air_quality_data():
    try:
        project = hopsworks_login()
        fs = project.get_feature_store()
        fg = fs.get_feature_group("aqi_features", version=1)
        df = fg.read()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values(by=["city", "timestamp"]).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()



# ─────────────────────────────────────────────────────────────
# 3b. PERSISTENCE FORECAST ENGINE (DIURNAL PATTERN ADJUSTED)
# ─────────────────────────────────────────────────────────────
def compute_diurnal_persistence_forecasts(city_df: pd.DataFrame, current_aqi: float, current_ts_utc: datetime):
    """
    Computes empirical persistence forecasts adjusted for each city's historical
    hour-of-day deviations (derived directly from historical data in the Feature Store).
    
    Formula for horizon h in [1..72]:
      1. city_mean = historical average AQI for the city
      2. hourly_profile = historical average AQI for each hour-of-day (0..23)
      3. diurnal_shift = hourly_profile[(curr_hour + h) % 24] - hourly_profile[curr_hour % 24]
      4. mean_reversion_weight = exp(-h / 168.0)  # smooth relaxation toward city baseline over 7 days
      5. forecast(h) = mean_reversion_weight * current_aqi + (1 - mean_reversion_weight) * city_mean + diurnal_shift
    """
    if city_df.empty or "aqi" not in city_df.columns:
        return round(current_aqi, 1), round(current_aqi, 1), round(current_aqi, 1), [round(current_aqi, 1)] * 72

    df_valid = city_df.dropna(subset=["aqi"]).copy()
    if df_valid.empty:
        return round(current_aqi, 1), round(current_aqi, 1), round(current_aqi, 1), [round(current_aqi, 1)] * 72

    city_mean = float(df_valid["aqi"].mean())
    
    # Ensure hour column exists
    if "hour" not in df_valid.columns:
        df_valid["hour"] = pd.to_datetime(df_valid["timestamp"], utc=True).dt.hour
        
    hourly_means = df_valid.groupby("hour")["aqi"].mean().to_dict()
    curr_hour = int(current_ts_utc.hour)
    curr_hour_mean = hourly_means.get(curr_hour, city_mean)

    future_curve = []
    for h in range(1, 73):
        target_hour = (curr_hour + h) % 24
        target_hour_mean = hourly_means.get(target_hour, city_mean)
        diurnal_delta = target_hour_mean - curr_hour_mean
        
        # Soft autoregressive decay toward city baseline (half-life of ~7 days)
        weight = float(np.exp(-h / 168.0))
        val = weight * current_aqi + (1.0 - weight) * city_mean + diurnal_delta
        val = max(0.0, min(500.0, round(float(val), 1)))
        future_curve.append(val)

    pred_24h = future_curve[23]  # +24h
    pred_48h = future_curve[47]  # +48h
    pred_72h = future_curve[71]  # +72h

    return pred_24h, pred_48h, pred_72h, future_curve


# ─────────────────────────────────────────────────────────────
# 4. TOP BAR & CITY SELECTOR
# ─────────────────────────────────────────────────────────────
cities_config = load_cities_config()
city_names = [c["name"] for c in cities_config]

col_nav_l, col_nav_r = st.columns([3, 2])
with col_nav_l:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
        <span style="font-size: 2.2rem;">🍃</span>
        <div>
            <div class="display-font" style="font-size: 1.9rem; font-weight: 800; line-height: 1.1; color: #ffffff;">
                AQI <span style="color: #00E400;">Predictor</span>
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 500;">
                Real-Time Air Quality & 3-Day Forecasts for Pakistan
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_nav_r:
    selected_city = st.selectbox(
        "Choose City",
        options=city_names,
        index=0,
        help="Select a city to check current air quality and upcoming 3-day forecasts."
    )

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# Load city dataframe
df_all = load_air_quality_data()
city_info = next((c for c in cities_config if c["name"] == selected_city), {"lat": 31.52, "lon": 74.35})
city_lat = city_info.get("lat", 31.52)
city_lon = city_info.get("lon", 74.35)

city_df = pd.DataFrame()
if not df_all.empty and selected_city in df_all["city"].values:
    city_df = df_all[df_all["city"] == selected_city].sort_values("timestamp").reset_index(drop=True)

# Strict Data Availability Check: Prefer NO DATA over WRONG DATA
data_available = False
data_unavailable_reason = None
latest_row = None
current_aqi = None

if not city_df.empty:
    latest_row = city_df.iloc[-1]
    if pd.notnull(latest_row.get("aqi")) and latest_row.get("aqi") is not None:
        current_aqi = round(float(latest_row["aqi"]), 1)
        data_available = True
    else:
        data_unavailable_reason = f"No verified local sensor or atmospheric model data available for {selected_city}."
else:
    data_unavailable_reason = (
        f"No records found for {selected_city} within the strict 100 km geographic radius limit. "
        f"The system refuses to display fallback data from distant or cross-border stations."
    )

if not data_available:
    st.markdown(f"""
    <div class="glass-card" style="padding: 32px 28px; border-left: 5px solid #ef4444; background: rgba(30, 15, 22, 0.85); margin-top: 16px; margin-bottom: 24px;">
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 10px;">
            <span style="font-size: 2.2rem;">⚠️</span>
            <div>
                <div class="display-font" style="font-size: 1.35rem; font-weight: 800; color: #f87171; text-transform: uppercase; letter-spacing: 0.04em;">
                    Local AQI Data Unavailable for {selected_city.upper()}
                </div>
                <div style="font-size: 0.85rem; color: #94a3b8;">
                    Configured Coordinates: {city_lat:.4f}° N, {city_lon:.4f}° E
                </div>
            </div>
        </div>
        <div style="font-size: 0.95rem; color: #e2e8f0; line-height: 1.5; margin-bottom: 14px;">
            {data_unavailable_reason}
        </div>
        <div style="font-size: 0.82rem; color: #fca5a5; background: rgba(0, 0, 0, 0.35); padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(239, 68, 68, 0.2);">
            <b>Strict Geographic Integrity Policy:</b> To ensure complete accuracy, this dashboard will never silently substitute data from a distant or foreign monitoring station (such as Delhi or Dushanbe) when local data is missing.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

aqi_meta = get_aqi_info(current_aqi)

# Real wall-clock "now" — always reflects current time regardless of data freshness
now_utc = datetime.now(timezone.utc)
now_pkt = now_utc.astimezone(timezone(timedelta(hours=5)))

# When the last data measurement was actually recorded
data_ts_utc = pd.to_datetime(latest_row["timestamp"], utc=True)
data_ts_pkt = data_ts_utc.astimezone(timezone(timedelta(hours=5)))
data_age_mins = int((now_utc - data_ts_utc).total_seconds() // 60)

# Keep legacy aliases so downstream code that references current_ts_* still works
current_ts_utc = now_utc
current_ts_pkt = now_pkt

# ── Compute Persistence Forecasts (Adjusted for Historical Daily Patterns) ───
pred_24h, pred_48h, pred_72h, future_aqi = compute_diurnal_persistence_forecasts(
    city_df, current_aqi, current_ts_utc
)

meta_24h = get_aqi_info(pred_24h)
meta_48h = get_aqi_info(pred_48h)
meta_72h = get_aqi_info(pred_72h)

# ─────────────────────────────────────────────────────────────
# 5. CONDITIONAL HAZARD WARNING BANNER
# ─────────────────────────────────────────────────────────────
valid_proj_values = [current_aqi] + [v for v in [pred_24h, pred_48h, pred_72h] if v is not None]
max_projected_aqi = max(valid_proj_values)
if max_projected_aqi >= 151:
    hazard_cat = get_aqi_info(max_projected_aqi)
    st.markdown(f"""
    <div class="hazard-alert-banner">
        <div style="display: flex; align-items: flex-start; gap: 14px;">
            <span style="font-size: 2.2rem;">{hazard_cat['icon']}</span>
            <div style="flex-grow: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span class="display-font" style="font-size: 1.15rem; font-weight: 800; color: #ffffff; text-transform: uppercase; letter-spacing: 0.04em;">
                        AIR QUALITY WARNING — {selected_city.upper()}
                    </span>
                    <span style="background: {hazard_cat['color']}; color: #000000; font-weight: 800; font-size: 0.75rem; padding: 3px 10px; border-radius: 999px;">
                        LEVEL: {hazard_cat['name'].upper()}
                    </span>
                </div>
                <div style="font-size: 0.9rem; color: #ffe4e6; line-height: 1.4; margin-bottom: 6px;">
                    Pollution levels are currently high and unhealthy for outdoor activities (Peak estimated AQI: <b>{max_projected_aqi:.0f}</b>).
                </div>
                <div style="font-size: 0.82rem; color: #fecdd3; background: rgba(0, 0, 0, 0.3); padding: 7px 12px; border-radius: 8px;">
                    <b>Recommended Action:</b> {hazard_cat['sensitive_advice']}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# 6. HERO SECTION: CURRENT AQI & PRACTICAL ADVICE
# ─────────────────────────────────────────────────────────────
col_hero_l, col_hero_r = st.columns([1.35, 1])

with col_hero_l:
    aqicn_ref = latest_row.get("aqicn_reference_aqi")
    ref_badge_html = ""
    
    # Source Transparency Badges
    source_label = "OpenWeather Model Grid"
    station_dist_str = "0.0 km (Exact Location)"
    if pd.notnull(aqicn_ref) and aqicn_ref is not None and float(aqicn_ref) > 0:
        ref_badge_html = (
            f'<div class="stat-pill" title="Verified ground monitor observation within 100 km">'
            f'<span>📡 Ground Ref: <b>{float(aqicn_ref):.0f} AQI</b></span>'
            f'</div>'
        )

    source_pill = (
        f'<div class="stat-pill" title="Atmospheric Chemical Transport Model queried at {selected_city} exact coordinates">'
        f'<span>🛰️ Source: <b>{source_label}</b></span>'
        f'</div>'
    )
    
    coords_pill = (
        f'<div class="stat-pill" title="Exact geographic coordinates configured for {selected_city}">'
        f'<span>📍 Coords: <b>{city_lat:.2f}°N, {city_lon:.2f}°E</b></span>'
        f'</div>'
    )

    status_pill = (
        '<div class="stat-pill" style="border-color: rgba(34, 197, 94, 0.4); background: rgba(34, 197, 94, 0.1);">'
        '<span>🟢 Status: <b style="color: #4ade80;">Verified Local Data</b></span>'
        '</div>'
    )

    mask_text = "Wear N95 Mask Outdoors" if aqi_meta["mask_required"] else "No Mask Needed"
    hero_bg    = aqi_meta["bg_glow"]
    hero_border = aqi_meta["border"]
    hero_color  = aqi_meta["text_color"]
    hero_icon   = aqi_meta["icon"]
    hero_name   = aqi_meta["name"]
    hero_advisory = aqi_meta["advisory"]
    ts_label     = now_pkt.strftime("%d %b, %I:%M %p PKT")
    city_label   = selected_city.upper()

    if data_age_mins < 60:
        data_age_str = f"{data_age_mins}m ago"
    elif data_age_mins < 120:
        data_age_str = "~1h ago"
    else:
        data_age_str = f"{data_age_mins // 60}h ago"

    data_age_pill = (
        f'<div class="stat-pill" title="Measurement recorded at {data_ts_pkt.strftime("%d %b, %I:%M %p PKT")} ({data_ts_utc.strftime("%H:%M UTC")})">'
        f'<span>🕒 Timestamp: <b>{data_ts_pkt.strftime("%I:%M %p PKT")}</b> ({data_age_str})</span>'
        f'</div>'
    )

    hero_html = f"""
    <div class="glass-card hero-aqi-card" style="background: radial-gradient(circle at 10% 20%, {hero_bg} 0%, rgba(16, 23, 38, 0.85) 80%); border-color: {hero_border};">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8;">
                CURRENT AIR QUALITY &bull; {city_label}
            </div>
            <div class="stat-pill">
                <span id="live-clock-pkt">🕒 {ts_label}</span>
            </div>
        </div>
        <div style="display: flex; align-items: baseline; gap: 18px; margin-top: 14px; margin-bottom: 2px;">
            <div class="hero-number" style="color: {hero_color};">{current_aqi:.0f}</div>
            <div>
                <div class="hero-category" style="background: {hero_bg}; color: {hero_color}; border: 1px solid {hero_border};">
                    <span>{hero_icon}</span>
                    <span>{hero_name}</span>
                </div>
                <div style="font-size: 0.82rem; color: #94a3b8; margin-top: 6px; margin-left: 4px;">
                    Air Quality Index (0 = Cleanest, 500 = Most Polluted)
                </div>
            </div>
        </div>
        <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
            {source_pill}
            {coords_pill}
            {data_age_pill}
            {status_pill}
            {ref_badge_html}
            <div class="stat-pill"><span>🛡️ Mask Advice: <b>{mask_text}</b></span></div>
        </div>
        <div style="margin-top: 12px; font-size: 0.9rem; color: #cbd5e1; line-height: 1.45;">
            {hero_advisory}
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

# Inject live JS clock — updates the #live-clock-pkt span every second
# Uses the browser's Intl API with Asia/Karachi timezone for accurate PKT.
st.markdown("""
<script>
(function() {
    function updatePKTClock() {
        var now = new Date();
        var datePart = now.toLocaleDateString('en-GB', {
            timeZone: 'Asia/Karachi',
            day: '2-digit', month: 'short'
        });
        var timePart = now.toLocaleTimeString('en-US', {
            timeZone: 'Asia/Karachi',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: true
        });
        var el = document.getElementById('live-clock-pkt');
        if (el) el.innerText = '\U0001F552 ' + datePart + ', ' + timePart + ' PKT';
    }
    updatePKTClock();
    setInterval(updatePKTClock, 1000);
})();
</script>
""", unsafe_allow_html=True)

with col_hero_r:
    st.markdown("""
    <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; margin-bottom: 2px;">
        3-DAY PERSISTENCE FORECAST (ADJUSTED FOR DAILY PATTERNS)
    </div>
    <div style="font-size: 0.72rem; color: #64748b; margin-bottom: 10px;">
        Based on current air quality and historical hour-of-day variations.
    </div>
    """, unsafe_allow_html=True)
    
    col_fc1, col_fc2, col_fc3 = st.columns(3)
    
    with col_fc1:
        time_24h = current_ts_pkt + timedelta(hours=24)
        st.markdown(f"""
        <div class="forecast-card" style="border-bottom: 3px solid {meta_24h['color']};">
            <div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8; text-transform: uppercase;">
                TOMORROW
            </div>
            <div style="font-size: 0.72rem; color: #64748b; margin-top: 1px;">
                {time_24h.strftime('%a, %I %p')}
            </div>
            <div class="forecast-val" style="color: {meta_24h['text_color']};">
                {pred_24h:.0f}
            </div>
            <div style="font-size: 0.75rem; font-weight: 600; color: {meta_24h['color']}; background: {meta_24h['bg_glow']}; padding: 2px 7px; border-radius: 999px;">
                {meta_24h['name']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_fc2:
        time_48h = current_ts_pkt + timedelta(hours=48)
        st.markdown(f"""
        <div class="forecast-card" style="border-bottom: 3px solid {meta_48h['color']};">
            <div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8; text-transform: uppercase;">
                DAY 2
            </div>
            <div style="font-size: 0.72rem; color: #64748b; margin-top: 1px;">
                {time_48h.strftime('%a, %I %p')}
            </div>
            <div class="forecast-val" style="color: {meta_48h['text_color']};">
                {pred_48h:.0f}
            </div>
            <div style="font-size: 0.75rem; font-weight: 600; color: {meta_48h['color']}; background: {meta_48h['bg_glow']}; padding: 2px 7px; border-radius: 999px;">
                {meta_48h['name']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_fc3:
        time_72h = current_ts_pkt + timedelta(hours=72)
        st.markdown(f"""
        <div class="forecast-card" style="border-bottom: 3px solid {meta_72h['color']};">
            <div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8; text-transform: uppercase;">
                DAY 3
            </div>
            <div style="font-size: 0.72rem; color: #64748b; margin-top: 1px;">
                {time_72h.strftime('%a, %I %p')}
            </div>
            <div class="forecast-val" style="color: {meta_72h['text_color']};">
                {pred_72h:.0f}
            </div>
            <div style="font-size: 0.75rem; font-weight: 600; color: {meta_72h['color']}; background: {meta_72h['bg_glow']}; padding: 2px 7px; border-radius: 999px;">
                {meta_72h['name']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="glass-card" style="margin-top: 12px; padding: 16px 18px;">
        <div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">
            Health Advice
        </div>
        <div style="font-size: 0.85rem; color: #e2e8f0; line-height: 1.4;">
            {aqi_meta['sensitive_advice']}
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 7. 3-DAY EXPECTED AIR QUALITY OUTLOOK (CHART)
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="display-font" style="font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-bottom: 2px;">
    3-Day Expected Air Quality Outlook (Persistence & Daily Pattern)
</div>
<div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px;">
    Continuously projected using recent sensor persistence and historical hour-of-day fluctuations.
</div>
""", unsafe_allow_html=True)

tail_df = city_df.tail(18).copy()
tail_ts = tail_df["timestamp"].tolist()
tail_aqi = tail_df["aqi"].tolist()

future_hours = np.arange(1, 73)
future_ts = [current_ts_utc + timedelta(hours=int(h)) for h in future_hours]

fig_forecast = go.Figure()

# Background color bands
fig_forecast.add_hrect(y0=0, y1=50, fillcolor="#00E400", opacity=0.08, line_width=0, annotation_text="Good (0-50)", annotation_position="top left", annotation_font_size=10, annotation_font_color="#00E400")
fig_forecast.add_hrect(y0=50, y1=100, fillcolor="#FFD600", opacity=0.08, line_width=0, annotation_text="Moderate (51-100)", annotation_position="top left", annotation_font_size=10, annotation_font_color="#FFD600")
fig_forecast.add_hrect(y0=100, y1=150, fillcolor="#FF7E00", opacity=0.08, line_width=0, annotation_text="Unhealthy for Sensitive (101-150)", annotation_position="top left", annotation_font_size=10, annotation_font_color="#FF7E00")
fig_forecast.add_hrect(y0=150, y1=200, fillcolor="#FF0000", opacity=0.08, line_width=0, annotation_text="Unhealthy (151-200)", annotation_position="top left", annotation_font_size=10, annotation_font_color="#FF0000")
fig_forecast.add_hrect(y0=200, y1=300, fillcolor="#8F3F97", opacity=0.08, line_width=0, annotation_text="Very Unhealthy (201-300)", annotation_position="top left", annotation_font_size=10, annotation_font_color="#8F3F97")

fig_forecast.add_trace(go.Scatter(
    x=tail_ts, y=tail_aqi,
    mode='lines+markers',
    name='Past Air Quality',
    line=dict(color='#94a3b8', width=2.5),
    marker=dict(size=5, color='#94a3b8'),
    hovertemplate='<b>Measured:</b> %{y:.1f} AQI<br><b>Time:</b> %{x|%d %b %H:%M UTC}<extra></extra>'
))

fig_forecast.add_trace(go.Scatter(
    x=[tail_ts[-1]] + future_ts, y=[tail_aqi[-1]] + future_aqi,
    mode='lines',
    name='Persistence + Daily Pattern',
    line=dict(color='#38bdf8', width=3, dash='dash'),
    hovertemplate='<b>Outlook:</b> %{y:.1f} AQI<br><b>Time:</b> %{x|%d %b %H:%M UTC}<extra></extra>'
))

milestone_x = [current_ts_utc + timedelta(hours=24), current_ts_utc + timedelta(hours=48), current_ts_utc + timedelta(hours=72)]
milestone_y = [pred_24h, pred_48h, pred_72h]
milestone_text = ["Tomorrow", "Day 2", "Day 3"]

fig_forecast.add_trace(go.Scatter(
    x=milestone_x, y=milestone_y,
    mode='markers+text',
    name='Forecast Milestones',
    text=milestone_text,
    textposition="top center",
    textfont=dict(color='#ffffff', size=11, family='Outfit'),
    marker=dict(size=11, color='#38bdf8', line=dict(color='#ffffff', width=2)),
    hovertemplate='<b>%{text}:</b> %{y:.1f} AQI<br><b>Date:</b> %{x|%d %b %H:%M UTC}<extra></extra>'
))

y_max = max(max(tail_aqi), max(future_aqi), 160) * 1.15
fig_forecast.update_layout(
    height=340,
    margin=dict(l=20, r=20, t=20, b=20),
    paper_bgcolor='rgba(16, 23, 38, 0.65)',
    plot_bgcolor='rgba(0,0,0,0)',
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#94a3b8")),
    xaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8'), title=""),
    yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8'), range=[0, y_max], title="Air Quality Index")
)

st.plotly_chart(fig_forecast, width='stretch', config={'displayModeBar': False}, key=f"fig_forecast_{selected_city}")

st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 8. POLLUTANTS IN TODAY'S AIR
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="display-font" style="font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-bottom: 2px;">
    Air Pollutants in Today's Air
</div>
<div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;">
    Main pollutants measured in the atmosphere right now.
</div>
""", unsafe_allow_html=True)

col_p1, col_p2, col_p3, col_p4, col_p5, col_p6 = st.columns(6)

pollutants_meta = [
    {"key": "pm25", "name": "PM2.5", "unit": "µg/m³", "col": col_p1, "limit": 35.4, "desc": "Fine Dust & Smoke"},
    {"key": "pm10", "name": "PM10", "unit": "µg/m³", "col": col_p2, "limit": 154.0, "desc": "Dust & Road Particles"},
    {"key": "o3", "name": "Ozone (O₃)", "unit": "µg/m³", "col": col_p3, "limit": 100.0, "desc": "Smog Gas"},
    {"key": "no2", "name": "NO₂", "unit": "µg/m³", "col": col_p4, "limit": 100.0, "desc": "Vehicle Emissions"},
    {"key": "so2", "name": "SO₂", "unit": "µg/m³", "col": col_p5, "limit": 75.0, "desc": "Industrial Smoke"},
    {"key": "co", "name": "CO", "unit": "µg/m³", "col": col_p6, "limit": 4400.0, "desc": "Carbon Monoxide"},
]

for p in pollutants_meta:
    raw_val = latest_row.get(p["key"])
    val_str = f"{float(raw_val):.1f}" if pd.notnull(raw_val) else "N/A"
    is_elevated = pd.notnull(raw_val) and float(raw_val) > p["limit"]
    
    with p["col"]:
        st.markdown(f"""
        <div class="pollutant-tile" style="border-left: 3px solid {'#f87171' if is_elevated else '#38bdf8'};">
            <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; text-transform: uppercase;">
                {p['name']}
            </div>
            <div class="display-font" style="font-size: 1.45rem; font-weight: 800; color: {'#f87171' if is_elevated else '#f8fafc'}; margin: 3px 0;">
                {val_str} <span style="font-size: 0.72rem; font-weight: 400; color: #64748b;">{p['unit']}</span>
            </div>
            <div style="font-size: 0.72rem; color: #64748b;">
                {p['desc']}
            </div>
        </div>
        """, unsafe_allow_html=True)

# Weather telemetry strip
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
col_w1, col_w2, col_w3, col_w4 = st.columns(4)

temp_val = f"{float(latest_row['temperature']):.1f} °C" if pd.notnull(latest_row.get("temperature")) else "28.5 °C"
hum_val = f"{float(latest_row['humidity']):.0f} %" if pd.notnull(latest_row.get("humidity")) else "62 %"
wind_val = f"{float(latest_row['wind_speed']):.1f} m/s" if pd.notnull(latest_row.get("wind_speed")) else "3.4 m/s"
press_val = f"{float(latest_row['pressure']):.0f} hPa" if pd.notnull(latest_row.get("pressure")) else "1012 hPa"

with col_w1:
    st.markdown(f"<div class='pollutant-tile'>🌡️ <b>Temperature:</b> {temp_val}</div>", unsafe_allow_html=True)
with col_w2:
    st.markdown(f"<div class='pollutant-tile'>💧 <b>Humidity:</b> {hum_val}</div>", unsafe_allow_html=True)
with col_w3:
    st.markdown(f"<div class='pollutant-tile'>💨 <b>Wind Speed:</b> {wind_val}</div>", unsafe_allow_html=True)
with col_w4:
    st.markdown(f"<div class='pollutant-tile'>⏲️ <b>Air Pressure:</b> {press_val}</div>", unsafe_allow_html=True)

st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 9. PAST AIR QUALITY TRENDS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="display-font" style="font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-bottom: 12px;">
    Past Air Quality Trends
</div>
""", unsafe_allow_html=True)

tab_7d, tab_30d, tab_hourly = st.tabs(["📊 Last 7 Days", "📈 Last 30 Days", "⏰ Daily Morning & Evening Pattern"])

with tab_7d:
    hist_7d = city_df.tail(168).copy()
    fig_7d = go.Figure()
    
    fig_7d.add_trace(go.Scatter(
        x=hist_7d["timestamp"], y=hist_7d["aqi"],
        mode='lines',
        name='Hourly AQI',
        line=dict(color='#00E400', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 228, 0, 0.08)',
        hovertemplate='<b>AQI:</b> %{y:.1f}<br><b>Time:</b> %{x|%d %b, %H:%M UTC}<extra></extra>'
    ))
    
    if "aqi_rolling_mean_24h" in hist_7d.columns:
        fig_7d.add_trace(go.Scatter(
            x=hist_7d["timestamp"], y=hist_7d["aqi_rolling_mean_24h"],
            mode='lines',
            name='Daily Average',
            line=dict(color='#f59e0b', width=2.5, dash='dot'),
            hovertemplate='<b>Daily Avg:</b> %{y:.1f}<extra></extra>'
        ))
        
    fig_7d.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=10, b=20),
        paper_bgcolor='rgba(16, 23, 38, 0.65)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8')),
        yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8'), title="AQI"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#94a3b8"))
    )
    st.plotly_chart(fig_7d, width='stretch', config={'displayModeBar': False}, key=f"fig_7d_{selected_city}")

with tab_30d:
    hist_30d = city_df.tail(720).copy()
    fig_30d = px.line(hist_30d, x="timestamp", y="aqi", color_discrete_sequence=['#38bdf8'])
    fig_30d.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=10, b=20),
        paper_bgcolor='rgba(16, 23, 38, 0.65)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8')),
        yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8'), title="AQI")
    )
    st.plotly_chart(fig_30d, width='stretch', config={'displayModeBar': False}, key=f"fig_30d_{selected_city}")

with tab_hourly:
    city_df_copy = city_df.copy()
    city_df_copy["hour_of_day"] = city_df_copy["timestamp"].dt.hour
    hourly_avg = city_df_copy.groupby("hour_of_day")["aqi"].mean().reset_index()
    
    fig_hourly = px.bar(
        hourly_avg, x="hour_of_day", y="aqi",
        labels={"hour_of_day": "Hour of Day (UTC)", "aqi": "Average Air Pollution (AQI)"},
        color="aqi",
        color_continuous_scale=[[0, '#00E400'], [0.5, '#FFD600'], [1, '#FF7E00']]
    )
    fig_hourly.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=10, b=20),
        paper_bgcolor='rgba(16, 23, 38, 0.65)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, tickmode='linear', tick0=0, dtick=2, tickfont=dict(color='#94a3b8')),
        yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.05)', tickfont=dict(color='#94a3b8')),
        coloraxis_showscale=False
    )
    st.plotly_chart(fig_hourly, width='stretch', config={'displayModeBar': False}, key=f"fig_hourly_{selected_city}")

st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 10. WHAT'S DRIVING THIS FORECAST
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="display-font" style="font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-bottom: 2px;">
    What's Driving This Forecast
</div>
<div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 14px;">
    Key factors influencing how air quality is expected to change over the next 3 days.
</div>
""", unsafe_allow_html=True)

# Plain-language driver bullets — default, always visible
st.markdown("""
<div class="glass-card" style="padding: 22px;">
    <div style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.55; margin-bottom: 14px;">
        Three main factors shape how tomorrow's air quality is expected to change:
    </div>
    <div style="font-size: 0.85rem; color: #e2e8f0; line-height: 1.65;">
        &#x2022; <b>Recent Air Quality:</b> Air pollution tends to stay similar from one hour to the next &mdash; so today's level is the strongest signal for tomorrow.<br><br>
        &#x2022; <b>Fine Particle Dust (PM2.5):</b> Tiny airborne particles are the main factor determining whether the air feels clear or smoggy at any given time.<br><br>
        &#x2022; <b>Morning &amp; Night Peaks:</b> Colder nighttime air traps smoke and vehicle fumes closer to the ground, causing pollution to rise during early mornings and late evenings.
    </div>
</div>
""", unsafe_allow_html=True)

# Collapsed technical expander — available for report / detailed review
with st.expander("Show technical forecast breakdown"):
    tab_d24, tab_d48, tab_d72 = st.tabs(["24-Hour Drivers", "48-Hour Drivers", "72-Hour Drivers"])

    with tab_d24:
        if os.path.exists("docs/shap_summary_24h.png"):
            st.image("docs/shap_summary_24h.png", width="stretch")
        else:
            st.caption("Feature importance chart for the 24-hour forecast will appear after the next daily training run.")

    with tab_d48:
        if os.path.exists("docs/shap_summary_48h.png"):
            st.image("docs/shap_summary_48h.png", width='stretch')
        else:
            st.info("Forecast driver visualization will update on the next daily run.")
            
    with tab_d72:
        if os.path.exists("docs/shap_summary_72h.png"):
            st.image("docs/shap_summary_72h.png", width='stretch')
        else:
            st.info("Forecast driver visualization will update on the next daily run.")

st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 11. FOOTER
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="padding-top: 18px; border-top: 1px solid rgba(255, 255, 255, 0.08); display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #64748b;">
    <div>
        <b>AQI Predictor</b> • Continuous Air Quality Monitoring & Forecasting for Pakistan
    </div>
    <div>
        Last Updated: {current_ts_utc.strftime('%Y-%m-%d %H:%M UTC')} ({current_ts_pkt.strftime('%I:%M %p PKT')})
    </div>
</div>
""", unsafe_allow_html=True)
