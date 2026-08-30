# PHASE 5 — CI/CD Automation

> Prerequisite: Phases 2 and 4 scripts (`feature_pipeline.py`, `training_pipeline.py`) both run correctly when triggered manually. See `brain.md` §6.

## Objectives
1. `feature_pipeline.py` runs automatically every hour, unattended.
2. `training_pipeline.py` runs automatically every day, unattended.
3. Secrets are securely handled (no keys in code or logs).

## Tasks
1. Confirm GitHub repo secrets are set (should already be done in Phase 1): `AQICN_API_KEY`, `OPENWEATHER_API_KEY`, `HOPSWORKS_API_KEY`, `HOPSWORKS_PROJECT_NAME`. Note: the supported city list lives in the **committed** `config/cities.yaml`, not in secrets — no per-city secret setup needed.
2. Write `.github/workflows/feature_pipeline.yml`:
   - Trigger: `schedule: cron: '0 * * * *'` + `workflow_dispatch` (so you can also trigger it manually from GitHub UI for testing).
   - Steps: checkout → setup-python → `pip install -r requirements.txt` → run `python src/feature_pipeline.py` with env vars pulled from secrets.
3. Write `.github/workflows/training_pipeline.yml`:
   - Trigger: `schedule: cron: '0 0 * * *'` + `workflow_dispatch`.
   - Same structure, runs `python src/training_pipeline.py`.
4. Add failure notifications (optional but recommended): GitHub Actions already emails on failure by default if configured; alternatively add a Slack/Discord webhook step.
5. Add a simple `tests/test_pipeline.py` with a couple of lightweight sanity tests (e.g., `data_fetcher` returns expected keys, `add_time_features` produces expected columns) that can optionally run as a CI step on every push (separate from the scheduled jobs).

## Testing / Definition of Done
- [ ] Manually triggering `feature_pipeline.yml` from the Actions tab succeeds (green check) and a new row appears in Hopsworks.
- [ ] Manually triggering `training_pipeline.yml` from the Actions tab succeeds and a new model version appears in the Model Registry.
- [ ] Wait for one real scheduled hourly run and confirm it fired automatically without manual trigger — check the Actions history timestamp.
- [ ] Confirm no secret values appear anywhere in the workflow logs (GitHub masks known secrets automatically, but double-check no derived/echoed values leak them).
- [ ] `tests/test_pipeline.py` passes locally (`pytest`).

**Do not proceed to Phase 6 until every box above is checked — at minimum, both workflows must have succeeded at least once via manual trigger, and one real automatic hourly run must be confirmed.**