# PHASE 1 — Setup & Data Access

> Read `brain.md` first. This phase has no ML in it — it's pure plumbing. Goal: by the end, you can run one script that prints a clean row of current AQI + weather data for each of your supported cities.

## Objectives
1. Repo, environment, and secrets are set up correctly.
2. Hopsworks (or Vertex AI) project is created and reachable from Python.
3. A `config/cities.yaml` file defining the fixed list of 5–10 supported cities.
4. A working `data_fetcher.py` that calls **both** AQICN and OpenWeather for any given city and returns one merged, clean dict.
5. `.env` based local secret management (never hardcoded keys).

## Tasks
1. Create GitHub repo `pearls-aqi-predictor`, initialize with the structure in `brain.md` §10.
2. Create and activate a Python virtual environment; add `requirements.txt` with: `requests`, `python-dotenv`, `pandas`, `hopsworks`, `pyyaml`.
3. Sign up for Hopsworks free tier → create a project → generate an API key.
4. Sign up for **both** AQICN and OpenWeather → get an API token/key for each.
5. Create `config/cities.yaml` listing 5–10 supported cities, each with `name`, `lat`, `lon`.
6. Create `.env.example` (committed) and `.env` (gitignored) listing: `AQICN_API_KEY`, `OPENWEATHER_API_KEY`, `HOPSWORKS_API_KEY`, `HOPSWORKS_PROJECT_NAME` (no per-city fields here — cities now live in `config/cities.yaml`, not `.env`).
7. Write `src/data_fetcher.py` with three functions (per `brain.md` §3 — dual API approach):
   - `fetch_aqicn_data(city, lat, lon) -> dict`: AQI + pollutants (pm25, pm10, o3, no2, so2, co, aqi, timestamp).
   - `fetch_openweather_data(lat, lon) -> dict`: temperature, humidity, wind_speed, pressure, timestamp.
   - `fetch_combined_data(city, lat, lon) -> dict`: calls both, rounds each timestamp to the nearest hour, merges into one row. If one source fails, keep the other's data and set a flag column (`aqi_source_ok` / `weather_source_ok` = False) instead of failing the whole row.
   - Handle API errors gracefully (retries/timeout) independently per source.
8. Write `src/utils.py` with: a `load_cities_config()` helper that reads `config/cities.yaml` into a list of dicts, a helper to round timestamps to the nearest hour, and (only if needed as a backup) a `compute_aqi_from_pollutants()` EPA breakpoint function in case AQICN's AQI field is ever missing for a station.
9. Verify Hopsworks connection with a throwaway script: `hopsworks.login()` + list/create a test Feature Group.
10. Add `.gitignore` (`.env`, `__pycache__`, `.venv`, etc.).

## Testing / Definition of Done
- [ ] `pip install -r requirements.txt` runs with no errors.
- [ ] `load_cities_config()` correctly parses `config/cities.yaml` and returns the expected list of city dicts.
- [ ] Running `python src/data_fetcher.py` (with a `if __name__ == "__main__"` test block) loops over all cities from the config and prints output from `fetch_aqicn_data()`, `fetch_openweather_data()`, and `fetch_combined_data()` for **each** — all with no `None`s in critical fields (pm25, aqi, temperature, timestamp).
- [ ] Confirm the merged row in `fetch_combined_data()` has matching/aligned timestamps from both sources (same hour) for every city tested.
- [ ] Temporarily break one API key (typo it) and confirm `fetch_combined_data()` still returns a row with the other source's data intact + the correct flag set to `False` — proves the fallback logic works.
- [ ] Temporarily make one city's coordinates invalid and confirm the loop logs an error for that city but still successfully processes the remaining cities (no single bad city halts the whole run).
- [ ] Hopsworks test script successfully logs in and confirms project access (prints project name/ID).
- [ ] `.env` is in `.gitignore` and is NOT visible in `git status` as tracked.
- [ ] Manually inspect the fetched data once per city: do the AQI/pollutant/weather values look realistic (sanity check against aqicn.org's public dashboard and a weather app)?

**Do not proceed to Phase 2 until every box above is checked.**