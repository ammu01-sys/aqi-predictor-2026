# Pearls AQI Predictor

An end-to-end serverless Machine Learning system that predicts the Air Quality Index (AQI) for a fixed set of supported cities for the next 3 days.

## System Architecture

The project is built around a multi-city configuration and consists of 4 decoupled components connected via the **Hopsworks Feature Store** and **Model Registry**:

1. **City List Configuration** (`config/cities.yaml`): A central, committed file containing the list of 5–10 supported cities, their latitudes, and longitudes.
2. **Feature Pipeline** (`src/feature_pipeline.py`): Loops over the configured cities and fetches weather and air quality data hourly from AQICN and OpenWeather APIs, processes features (calculating lag and rolling metrics per city), and stores them in the Feature Store.
3. **Training Pipeline** (`src/training_pipeline.py`): Periodically retrieves features from the Feature Store, trains baseline, tree-based, and deep learning pooled models (using the city as an encoded categorical feature), and registers the best-performing model to the Model Registry.
4. **Web App / Dashboard** (`app/streamlit_app.py`): Contains a city dropdown selector that displays current air quality metrics, 3-day forecasts, historical trends, and SHAP-based feature importance for the selected city.
5. **CI/CD Automation** (GitHub Actions): Automates the feature pipeline hourly and the training pipeline daily, looping over all configured cities.


## Setup Instructions

1. Clone the repository.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   > **Note for Windows users without Microsoft C++ Build Tools**: If `pip install` fails while building `twofish`, install `hopsworks` and `pyjks` with `--no-deps` to bypass compilation:
   > ```bash
   > pip install hopsworks pyjks --no-deps
   > pip install javaobj-py3 pyasn1 pyasn1-modules pycryptodomex
   > pip install -r requirements.txt
   > ```
4. Copy `.env.example` to `.env` and fill in the required API keys and configuration.

