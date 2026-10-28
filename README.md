# F1 Performance Intelligence

FastF1 ingestion → database → FastAPI analytics/forecast/strategy services → React (JSX only) dashboard.

## Status

| Area | State |
|---|---|
| Ingestion (idempotent, validated, null-safe) | Implemented; tested on synthetic sessions. **Not yet run against live FastF1 data.** |
| DB models (all tables in the spec) | Implemented. Alembic migrations **not generated yet**; dev uses `create_all`. |
| API: seasons, events, standings, session laps/drivers/compare/telemetry, forecasts, strategy, ingestion jobs | Implemented |
| Championship forecast | Baseline (points-per-race form + Plackett-Luce Monte Carlo). Backtested on 2024 only: beats a uniform baseline; a sharpening exponent (α=2.5, chosen by expanding-window validation) fixed most of the under-confidence. Cross-season check (2023↔2024): α chosen on one season transfers to the other (best α is 2.5 to 3.0 on a grid up to 6.0). See `docs/evaluation-report.md` and `docs/evaluation-cross-season.md`. Regenerate with `python scripts/run_backtest.py 2024`. |
| Strategy simulator | Quadratic tyre model with fuel proxy, model-vs-model delta, lap-noise interval |
| Frontend: Season, Race Explorer, Strategy Lab, Driver and Constructor pages | Implemented and "Pit wall" design (sidebar, team colours, KPI strip, points-progression chart); checked in the browser at 1600 px, 375 px and 320 px widths (emulated; real-device touch not tested) |
| Race predictions page (`/predictions`) | **All planned phases done.** Forecast per upcoming race (classification, win/podium/points/DNF probabilities, position heatmap, constructor points); pre-qualifying mode upgrades itself to post-qualifying once that weekend's qualifying is ingested. **Snapshots**: each forecast is saved before its race (`race_forecast_snapshots`), replaced only while the race has not been run and frozen for good afterwards; `ingest_season.py` saves fresh snapshots automatically when it ingests something (skip with `--no-snapshot`), or run `python -m scripts.snapshot_forecasts 2026`. **Track record panel**: scores saved forecasts against results once each race is ingested (the honest test; empty until the first snapshotted race is run, first five snapshots taken 2026-10-28 for rounds 19 to 23), plus a clearly labelled retrospective replay of past races (not frozen and optimistic: settings were tuned on those races). Evidence for model choices: `docs/evaluation-race-model.md`, `docs/evaluation-grid-model.md`. Grid penalties and pit-lane starts are not reflected. **Circuits**: a team-by-circuit pace effect was tested (`docs/evaluation-circuit-effect.md`, rule written first) and did not predict better, so before qualifying every upcoming race gets the same forecast (the page says so); they separate once qualifying is ingested. |
| Circuit Lab (3D) | Implemented (Three.js / React Three Fiber): telemetry replay on a track reconstructed from position data, speed-coloured track, two-driver comparison with distance-aligned time delta. Telemetry is stored for 2024 qualifying at 6 circuits (Bahrain, Monaco, Silverstone, Monza, Singapore, Abu Dhabi); ingest more with `scripts/ingest_season.py 2024 --telemetry --sessions Q --rounds N`. Geometry is approximate and flat; corner markers are speed minima. |

## Run locally

```bash
cd backend
py -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env    # leave DATABASE_URL unset-> SQLite, or point at PostgreSQL
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

Ingest a session (needs network; first load is slow, then cached in `data/cache`):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingestion/jobs -H "Content-Type: application/json" \
  -d '{"year":2024,"event":"Monaco","session_type":"R"}'
```

Tests: `cd backend && python -m pytest` and `cd frontend && npm test`.

## Data in the local database

2023 to 2026 (2026 is in progress): races, sprints, sprint qualifying and qualifying for every round held so far;
qualifying telemetry for 2024 to 2026. Standings were checked against official/Jolpica totals for 2023 to 2026.

Refresh the running season after each race weekend (only fetches sessions not yet stored):

```bash
cd backend
.venv\Scripts\python scripts/ingest_season.py 2026 --sessions R,S,SQ --new-only
.venv\Scripts\python scripts/ingest_season.py 2026 --sessions Q --telemetry --new-only
```

## Known modelling caveats

- The sharpening exponent (alpha) was chosen on 2023/2024; the 2026 regulations are new, so its forecasts are untested there.

- Tyre age, age² and the lap-number fuel proxy are correlated, so individual coefficients are weakly identified; only the combined stint lap-time change is reliable.
- Strategy intervals cover lap-to-lap noise only (no traffic, safety cars, weather, rivals).
- Championship tie-break is simplified (simulated wins, then random), not the full FIA countback.
- Sprint-race scoring is modelled but sprints remaining are not derived from the calendar yet.
