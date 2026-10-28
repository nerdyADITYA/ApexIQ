# F1 Performance Intelligence Dashboard (ApexIQ)

A full-stack data-science project that downloads real Formula 1 data, stores it in a database, analyses driver and
team performance, simulates pit-stop strategies, and **forecasts upcoming races and the championship with
probabilities**. Every forecast model was tested on past races before it was allowed into the app.

**Stack:** Python (FastF1, pandas, NumPy, SciPy, SQLAlchemy, FastAPI) and React (Vite, TanStack Query, Recharts,
Three.js). Frontend is plain JavaScript/JSX, no TypeScript.

```
FastF1 (official F1 timing data)
      │  ingestion scripts / API job
      ▼
SQLite database  ──►  analytics + models (pure Python)  ──►  FastAPI (JSON)  ──►  React dashboard
```

---

## Contents

1. [Problem statement and objectives](#1-problem-statement-and-objectives)
2. [What the system does (feature list)](#2-what-the-system-does-feature-list)
3. [Architecture](#3-architecture)
4. [Technology choices](#4-technology-choices)
5. [Folder structure: which file does what](#5-folder-structure-which-file-does-what)
6. [Module 1: Data ingestion](#6-module-1-data-ingestion)
7. [Module 2: Database design](#7-module-2-database-design)
8. [Module 3: Analytics](#8-module-3-analytics)
9. [Module 4: Forecasting models](#9-module-4-forecasting-models)
10. [Module 5: Model evaluation (backtests)](#10-module-5-model-evaluation-backtests)
11. [Module 6: Forecast snapshots and track record](#11-module-6-forecast-snapshots-and-track-record)
12. [Module 7: Strategy Lab (pit-stop simulator)](#12-module-7-strategy-lab-pit-stop-simulator)
13. [Module 8: Telemetry and the 3D Circuit Lab](#13-module-8-telemetry-and-the-3d-circuit-lab)
14. [Module 9: REST API](#14-module-9-rest-api)
15. [Module 10: Frontend](#15-module-10-frontend)
16. [Testing](#16-testing)
17. [How to run it](#17-how-to-run-it)
18. [Honest limitations](#18-honest-limitations)
19. [Future work](#19-future-work)
20. [Viva preparation: likely questions and answers](#20-viva-preparation-likely-questions-and-answers)

---

## 1. Problem statement and objectives

Formula 1 produces a huge amount of timing and telemetry data, but fans and analysts mostly see raw results.
This project turns the data into answers:

- Who is really quick, after removing luck, traffic and strategy noise?
- How does a team compare with its rivals, and a driver with their teammate?
- What would have happened with a different pit-stop strategy?
- **What is the probability that each driver wins, reaches the podium, scores points or retires in the next race,
  and who wins the championship?**

Objectives:

1. Ingest real data from FastF1 reliably (re-runnable, no duplicates).
2. Store it in a proper relational schema.
3. Compute clear, defensible performance metrics.
4. Build probabilistic forecasts and **measure honestly** whether they work.
5. Present everything in a responsive dashboard.

The project's guiding rule is **honesty about uncertainty**: forecasts are probabilities, caveats are shown on the
page, and a model that did not beat its baseline was not adopted.

## 2. What the system does (feature list)

| Page / feature | What the user sees |
|---|---|
| **Dashboard** | Standings, championship win probabilities, points progression chart for the top drivers |
| **Drivers / Driver detail** | Season profile: race pace vs field, qualifying, reliability, teammate gap, per-circuit history |
| **Constructors / Constructor detail** | Team pace, both drivers' contribution, points, reliability |
| **Race Explorer** | Lap-time chart for race sessions with safety-car / VSC / red-flag shading and pit-stop markers |
| **Strategy Lab** | Tyre-degradation model for a race, simulate your own pit strategy vs the real one, with a time-difference graph and uncertainty band |
| **Predict** (`/predictions`) | Full forecast for each upcoming race: predicted classification, win/podium/points/DNF chances, finishing-position heatmap, constructor points, and a track record |
| **Circuit Lab (3D)** | Track rebuilt from position data, animated telemetry replay, two-driver lap comparison with time delta |

## 3. Architecture

Three layers with one-way dependencies:

1. **Data layer** (`backend/app/data`, `backend/scripts`): downloads from FastF1, cleans, validates and writes to the
   database. The browser never touches FastF1.
2. **Logic layer** (`backend/app/analytics`, `ml`, `strategy`, `services`): pure functions that take pandas
   DataFrames and return numbers. They have no web or database code, so they are easy to unit-test. `services`
   is the thin glue that reads the database into DataFrames and calls them.
3. **Presentation layer** (`backend/app/api`, `frontend/`): FastAPI exposes JSON; React renders it.

Why this split: the maths can be tested without a database, the API stays small, and the frontend only ever sees
JSON.

## 4. Technology choices

| Tool | Used for | Why |
|---|---|---|
| FastF1 | Official timing, results, telemetry | Free access to real F1 data with a local cache |
| pandas / NumPy / SciPy | Tables, simulation, Spearman correlation | Standard data-science stack |
| SQLAlchemy 2 + SQLite | ORM and database | SQLite needs no setup for development; same models run on PostgreSQL |
| FastAPI + Pydantic | REST API | Automatic validation and interactive docs at `/docs` |
| pytest | Backend tests | Standard |
| React 18 + Vite | Frontend | Fast development, component model |
| TanStack Query | Fetching and caching API data | Handles loading, errors and caching |
| Recharts | 2D charts | Simple React charting |
| Three.js / React Three Fiber / drei | 3D Circuit Lab | WebGL in React |
| Vitest + Testing Library | Frontend tests | Works with Vite |
| Docker Compose | Optional Postgres + backend | Provided as a starting point for deployment |

## 5. Folder structure: which file does what

```
ApexIQ/
├── README.md                       this document
├── docker-compose.yml              Postgres + backend containers (deployment starting point)
├── .env.example                    environment variables (DATABASE_URL, CORS_ORIGINS ...)
├── docs/                           written evidence for every modelling decision (see section 10)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── data/                       local DB and FastF1 cache (NOT in git; rebuilt by ingestion)
│   ├── app/
│   │   ├── main.py                 creates the FastAPI app, CORS, mounts all routers under /api/v1
│   │   ├── core/
│   │   │   ├── config.py           settings from environment (DB url, cache dir, CORS)
│   │   │   ├── database.py         SQLAlchemy engine/session, get_db dependency
│   │   │   └── logging.py          logging setup
│   │   ├── data/                   ── Module 1: ingestion
│   │   │   ├── fastf1_loader.py    thin wrapper around FastF1 (load session, schedule, laps, telemetry)
│   │   │   ├── transformations.py  pure cleaning: time conversion, lap classification, pit-stop derivation
│   │   │   ├── validation.py       request validation and lap-data quality checks
│   │   │   └── ingestion.py        idempotent write of a session into the database
│   │   ├── models/
│   │   │   ├── database_models.py  ── Module 2: all SQLAlchemy tables
│   │   │   └── schemas.py          Pydantic request/response shapes
│   │   ├── analytics/              ── Module 3
│   │   │   ├── driver_metrics.py   lap cleaning, pace summary, teammate delta, sector deltas
│   │   │   ├── season_metrics.py   race pace table, driver/constructor profiles, circuit history
│   │   │   ├── pit_stop_analysis.py robust pit-lane time-loss estimator
│   │   │   ├── tire_degradation.py tyre degradation regression
│   │   │   └── telemetry.py        telemetry cleaning, distance alignment, delta time, track geometry
│   │   ├── ml/                     ── Modules 4 and 5
│   │   │   ├── simulation.py       Plackett-Luce Monte Carlo, points tables, championship simulation
│   │   │   ├── championship_model.py season championship forecast
│   │   │   ├── features.py         per-race feature table, team name lineage, team-circuit effects
│   │   │   ├── evaluation.py       form strengths and scoring/backtest helpers for the championship model
│   │   │   ├── race_model.py       configurable race-outcome model and simulator
│   │   │   ├── race_forecast.py    the production forecast for one upcoming race
│   │   │   ├── race_backtest.py    forward-chaining backtest harness for race models
│   │   │   └── track_record.py     scoring saved forecasts against actual results
│   │   ├── services/               glue between database and logic
│   │   │   ├── frames.py           database to DataFrames (entries, laps, results, pit stops)
│   │   │   ├── forecast_service.py upcoming races, build and save forecast snapshots
│   │   │   └── track_record_service.py frozen and replay track records
│   │   ├── strategy/               ── Module 7
│   │   │   ├── simulator.py        compare strategies, per-lap difference profile, candidate search
│   │   │   └── constraints.py      F1 rules checks (compounds, min stint, max stops)
│   │   └── api/v1/                 ── Module 9 (one router per area)
│   │       ├── seasons.py          seasons, events, standings
│   │       ├── sessions.py         session overview, drivers, laps, compare, telemetry
│   │       ├── analytics.py        driver/constructor profiles, tracks, progression
│   │       ├── telemetry.py        telemetry sessions, lap comparison, circuit geometry
│   │       ├── predictions.py      race forecasts, snapshots, track record
│   │       ├── championships.py    driver and constructor championship forecasts
│   │       ├── strategies.py       strategy simulation
│   │       └── ingestion.py        start and poll ingestion jobs
│   ├── scripts/                    command-line tools
│   │   ├── ingest_season.py        ingest a whole season (races, sprints, qualifying, telemetry)
│   │   ├── ingest_session.py       ingest one session
│   │   ├── merge_circuit_aliases.py one-off repair: merge duplicate circuit names
│   │   ├── snapshot_forecasts.py   save forecasts for upcoming races
│   │   └── run_*.py                reproducible backtests that write docs/evaluation-*.md
│   └── tests/                      pytest suite
└── frontend/
    ├── vite.config.js, package.json, index.html
    └── src/
        ├── main.jsx                React entry, router, query client
        ├── App.jsx                 layout, sidebar navigation, routes (Circuit Lab is lazy-loaded)
        ├── pages/                  one file per screen (Dashboard, Drivers, DriverDetail, Constructors,
        │                           ConstructorDetail, RaceExplorer, StrategyLab, Predictions, CircuitLab)
        ├── components/
        │   ├── layout/PageHeader.jsx   page title and labelled Race/Season selectors
        │   ├── cards/              Kpi, Stat, TeamBarRow
        │   ├── charts/             StintTimeline, StrategyResult, TrackRecord
        │   └── common/             QueryState (loading/error/empty), ErrorBoundary
        ├── three/                  3D: CircuitScene, CircuitTrack, DriverMarker, CameraControls,
        │                           TelemetryPlayback, TelemetryCharts, LapComparison
        ├── hooks/useSeason.jsx     shared selected-season state
        ├── services/api.js         every API call in one place
        ├── utils/                  teams.js (team colours), sessions.js (session names), telemetry.js
        └── styles/app.css          the "Pit wall" design (responsive, 44 px tap targets)
```

## 6. Module 1: Data ingestion

**Goal:** get real data into the database safely, and be able to re-run it any time.

**Files:** `data/fastf1_loader.py`, `data/transformations.py`, `data/validation.py`, `data/ingestion.py`,
`scripts/ingest_season.py`, `scripts/ingest_session.py`, API `api/v1/ingestion.py`.

**How it works**

1. `validation.validate_request` checks year, event and session type (`R` race, `Q` qualifying, `S` sprint,
   `SQ`/`SS` sprint qualifying, `FP1-3`).
2. `fastf1_loader.load_session` downloads the session (cached on disk under `backend/data/cache`, so the second
   run is fast and offline-friendly).
3. `transformations` cleans it: converts FastF1's time deltas to milliseconds, classifies each lap (valid,
   in-lap, out-lap, neutralised by safety car/VSC/red flag, wet), and derives pit stops from lap data.
4. `validation.validate_laps` reports quality problems (missing times, etc.).
5. `ingestion.ingest_loaded_session` writes everything inside **one transaction**.

**Key design ideas**

- **Idempotent:** running the same ingestion twice does not create duplicates. Entities (season, circuit, event,
  driver, constructor) are get-or-create; a session's laps, pit stops and telemetry are *replaced* inside the
  transaction, so a failure leaves the old data untouched.
- **Schedule upsert never resets status:** a bug where re-running reset already-loaded sessions was found and fixed,
  with a regression test.
- **Circuit aliases:** FastF1 names the same circuit differently across seasons (Yas Marina / Yas Island, Monte
  Carlo / Monaco). `CIRCUIT_ALIASES` maps them to one name, otherwise a circuit's history would be split.
- **Telemetry** is stored only for the fastest lap of selected sessions and **down-sampled to about 400 points**,
  to keep the database small.
- `ingest_season.py` supports `--sessions R,S,SQ,Q`, `--telemetry`, `--rounds`, `--new-only` (fetch only what is
  missing, used to keep the running 2026 season up to date), skips sessions in the future, and finally saves
  fresh forecast snapshots (skip with `--no-snapshot`).

## 7. Module 2: Database design

**File:** `models/database_models.py` (SQLAlchemy 2 declarative models). The database is SQLite by default
(`backend/data/f1_dev.db`); `DATABASE_URL` switches it to PostgreSQL.

| Table | Holds |
|---|---|
| `seasons`, `circuits`, `events` | Year, circuit, each Grand Prix weekend |
| `sessions` | One row per session (R, Q, S, SQ ...) with a loaded/not-loaded status |
| `drivers`, `constructors` | People and teams |
| `session_entries` | A driver in a session (team, grid, finish, points, status) |
| `laps` | Every lap: times, sectors, compound, tyre age, validity flags, track status |
| `pit_stops` | Derived pit stops |
| `telemetry_points` | Down-sampled fastest-lap telemetry (speed, throttle, brake, gear, x/y) |
| `weather_observations` | Weather table (schema only; not populated, see limitations) |
| `driver_standings`, `constructor_standings` | Standings tables |
| `predictions`, `strategy_scenarios` | Stored forecast / strategy records |
| `race_forecast_snapshots` | A forecast saved *before* a race (unique per year, round, mode; JSON payload) |
| `ingestion_runs` | Audit log of ingestion jobs |

Relations: season → events → sessions → session_entries → laps/pit_stops/telemetry. Foreign keys and uniqueness
constraints are what make ingestion idempotent.

> Alembic migrations are not generated yet; development uses `create_all` (see Future work).

## 8. Module 3: Analytics

All functions are pure (DataFrame in, numbers out) in `backend/app/analytics`.

### 8.1 Pace (`driver_metrics.py`, `season_metrics.py`)
- **Clean laps:** only valid laps within **107%** of the driver's own median are used (removes in/out laps, crashes,
  slow laps).
- **Pace delta:** a driver's median clean lap compared with the *field median in the same race*, as a **percentage**
  (negative = faster). Percentages make short and long circuits comparable.
- **Teammate gap:** the same comparison between two drivers in the same car, which removes the car from the
  comparison and isolates the driver.
- A driver needs at least **15 clean laps** in a race to get a pace figure (`MIN_CLEAN_LAPS`).
- `driver_profile`, `constructor_profile` and `circuit_history` assemble these into what the Driver and
  Constructor pages display.

### 8.2 Pit-lane time loss (`pit_stop_analysis.py`)
A stop costs `(in-lap + out-lap) − 2 × the driver's local clean pace` around that stop. The naive version gave
30–49 s in about a sixth of real races, so the estimator is defensive:
local baseline (6 laps either side), skip stops under safety car/VSC/red flag and wet stops, drop values outside
8–50 s as measurement artefacts, need at least 4 stops and a small spread, take the **median**, and fall back to
**22 s** (the measured median over 2023–2026) when the race is too messy. It reports where the number came from.

### 8.3 Tyre degradation (`tire_degradation.py`)
`lap_time = compound_base + b1·age + b2·age² + b3·lap_number + noise`. Lap number is a **proxy for fuel load**
(cars get lighter and faster). Needs at least 8 laps per compound. It is interpretable rather than clever. The
three terms are correlated, so individual coefficients are weak; only the combined lap-time change over a stint is
trusted.

### 8.4 Telemetry (`telemetry.py`) — see Module 8.

## 9. Module 4: Forecasting models

### 9.1 The core idea: Plackett–Luce + Monte Carlo (`ml/simulation.py`)
Each driver has a **strength**. A finishing order is sampled so that stronger drivers tend to finish ahead but
anything can happen. This is the **Plackett–Luce** model, sampled with the **Gumbel trick**: add Gumbel noise to
`log(strength)` and sort. Repeat 10,000–20,000 times. The fraction of simulations where a driver finished P1 is
their **win probability**; likewise podium (top 3), points (top 10) and the full P1…P20 grid shown as the heatmap.
Retirements are simulated separately with a per-driver chance, and retirees finish behind all finishers.

Why Monte Carlo: it gives a full probability distribution (not just a ranking), and constructor and championship
outcomes come out consistent with the driver results because they are summed from the *same* simulated races.

### 9.2 Strength from form (`ml/evaluation.py` → `form_strengths`)
Strength = the driver's **points per race this season**, shrunk toward the field average (small samples are
unreliable), then **sharpened**: `log strength = α · log(form)`. Without sharpening the model is under-confident
(it thinks the top driver is not much better than the rest). **α = 2.5** for the championship model was chosen by
expanding-window validation and re-checked across seasons (best α was 2.5–3.0).

### 9.3 Championship forecast (`ml/championship_model.py`)
Simulates all remaining races of the season with the strengths above and the season's points rules
(`race_points_table`, sprint points), adding points to what each driver already has. Output: probability of
winning the driver and constructor championship and expected final points. Only results that already happened are
used. Limits: simplified tie-break (not the full FIA countback) and sprints remaining are not derived from the
calendar.

### 9.4 Race forecast (`ml/race_model.py`, `ml/race_forecast.py`)
`race_forecast.forecast_race` is what the Predict page shows. It works in **two modes** and switches itself:

| Mode | When | Model |
|---|---|---|
| **Pre-qualifying** | Qualifying not yet ingested | Form strength only (baseline), shrunk retirement rates |
| **Post-qualifying** | Qualifying order available for ≥ 80% of the field | `strength = form^1.5 × grid_position^−2.0`; qualifying order is the starting grid |

- **Retirement rates** (`dnf_probabilities`) are estimated per driver and per team from earlier races and
  **shrunk toward the average** (a driver with one DNF is not "unreliable"). Adopted because it improved
  retirement log-loss (0.449 → 0.393).
- **Lineup:** taken from the latest race (or from who actually qualified in post-qualifying mode); drivers who left
  are listed in notes.
- **Output:** per driver expected position, win/podium/points/DNF probability, position probabilities, expected
  points; per team expected points; plus caveats generated for the situation.
- **Team lineage** (`features.canonical_team`) follows renames (RB / AlphaTauri → Racing Bulls, Kick Sauber / Alfa
  Romeo → Audi).

### 9.5 "Why does every upcoming race look the same?"
Before qualifying, all upcoming races are forecast from the same results, so they come out identical. We tested a
**team-by-circuit effect** (does a team do better at a track than its season average?) and it did **not** predict
better than the plain model (docs/evaluation-circuit-effect.md), so it was **not adopted** and the page states this.
Forecasts separate after qualifying because the grid differs.

## 10. Module 5: Model evaluation (backtests)

**Principle:** never trust a model on the data it was tuned on. All backtests are **forward-chaining**: each race is
predicted using only earlier races, parameters are chosen on earlier seasons only, then applied unchanged.

**Metrics** (computed in `ml/evaluation.py`, `ml/race_backtest.py`)
- **Log loss / Brier score** for win, podium and top-10 events: measures *probability quality*, punishes
  confident wrong answers. Lower is better. A uniform model (everyone equal) is the reference.
- **Calibration table:** when the model says 30%, does it happen about 30% of the time?
- **Spearman rank correlation** and **mean position error** for how good the predicted *order* is.
- **Paired bootstrap 95% intervals** across races: tells whether a difference between two models is real or noise.

**Pre-registered adoption rule** (written *before* running): a new model is adopted only if its improvement over
the current one has a 95% interval entirely below zero for podium **and** top-10 log loss, it is not materially
worse on win log loss, and it does not hurt rank correlation. This stops us from picking whatever looks good
after the fact.

| Experiment | Script → document | Outcome |
|---|---|---|
| Sharpening (α) on championship | `run_backtest.py` → `evaluation-report.md` | Adopted, α = 2.5 |
| Cross-season transfer | `run_cross_season.py` → `evaluation-cross-season.md` | α transfers between 2023 and 2024 |
| Four-season rolling | `run_rolling.py` → `evaluation-rolling.md` | Sharpened model beats uniform with intervals excluding 0 |
| Richer strength model (pace + qualifying) | `run_race_backtest.py` → `evaluation-race-model.md` | **Not adopted**: ordering better but probability gains did not clear zero. Shrunk retirement rates **adopted** |
| Grid (qualifying) model | `run_grid_backtest.py` → `evaluation-grid-model.md` | **Adopted** for post-qualifying (54 races); a per-circuit grid weight was **not adopted** |
| Team-by-circuit effect | `run_circuit_backtest.py` → `evaluation-circuit-effect.md` | **Not adopted** |

Honest note: some settings (the grid exponent) were chosen on all seasons, so the replay of past races is
optimistic. This is stated wherever replay results are shown.

## 11. Module 6: Forecast snapshots and track record

A forecast made *after* the race is worthless as proof. So:

- `services/forecast_service.save_snapshot` stores the forecast in `race_forecast_snapshots` **before** the race.
  It can be replaced while the race has not been run; once the race is ingested it is **frozen forever**
  (`RaceAlreadyRun` is raised on any attempt to overwrite).
- `ml/track_record.score_forecast` scores a snapshot against the real result (winner probability, podium hits,
  Spearman, position error); `summarise` aggregates; `calibration_table` bins predicted vs observed.
- `services/track_record_service` provides two views, switchable on the page:
  - **Saved before the race** (`frozen`): the genuine test. Empty until a snapshotted race is run.
  - **Retrospective replay** (`replay`): re-forecasts past races. Clearly labelled **not frozen and optimistic**.
    Currently 14 scored 2026 races; post-qualifying, the winner was in the predicted top 3 in 13 of 14.

## 12. Module 7: Strategy Lab (pit-stop simulator)

**Files:** `strategy/simulator.py`, `strategy/constraints.py`, `analytics/tire_degradation.py`,
`analytics/pit_stop_analysis.py`, API `strategies.py`, page `StrategyLab.jsx`, chart `StrategyResult.jsx`.

1. Fit the tyre degradation model for the chosen race (above).
2. The page starts from the **real strategy** the driver ran (compounds and pit laps); the user edits it.
3. `check_strategy` validates it: one more compound than stops, at most 4 stops, pit laps strictly increasing and
   inside the race, every stint at least 3 laps, and in a dry race only SOFT/MEDIUM/HARD with at least two
   different compounds.
4. `simulate_strategy` predicts every lap's time for both the real and candidate strategy with the **same** model
   and adds the pit-lane loss per stop. The result is a **model-versus-model difference**, which cancels much of the
   model's own bias. A Monte-Carlo resample of lap residuals gives a 90% band.
5. `strategy_profile` returns the running time difference per lap, drawn as a chart; the verdict is coloured only
   if the interval excludes zero (otherwise "within uncertainty").
6. `enumerate_candidates` / `best_strategy` can search one- and two-stop plans.

Limits: no traffic, safety cars, weather or rivals; the band covers lap-to-lap noise only.

## 13. Module 8: Telemetry and the 3D Circuit Lab

**Files:** `analytics/telemetry.py`, API `telemetry.py`, `three/*`, `pages/CircuitLab.jsx`, `utils/telemetry.js`.

- **Cleaning:** sort, drop duplicates, convert FastF1 X/Y (1/10 m) to metres.
- **Track geometry:** `build_centerline` smooths one lap's x/y positions into a closed loop;
  `approximate_corners` marks speed minima; `sector_markers` marks sector boundaries. It is **approximate and flat**
  (no elevation), not surveyed geometry.
- **Two-driver comparison:** the two laps have slightly different integrated distances, so each is **rescaled to a
  common length**, resampled by distance (300 points) and the time axis is scaled to the official lap time.
  `delta_time` then gives the cumulative time gap along the lap (this fixed an error of up to 0.4 s).
- **Frontend:** React Three Fiber draws the track coloured by speed, animated car markers (disc vs diamond for
  driver A/B), playback controls, synchronised speed/throttle/brake/gear charts and the delta chart.
- Telemetry is stored for qualifying sessions at selected circuits; ingest more with
  `scripts/ingest_season.py 2024 --telemetry --sessions Q --rounds N`.

## 14. Module 9: REST API

All routes are under `/api/v1`. Interactive documentation is generated automatically at
`http://localhost:8000/docs`.

| Method and path | Purpose |
|---|---|
| `GET /seasons`, `GET /events?season=` | Seasons and race weekends |
| `GET /seasons/{year}/standings` | Driver and constructor standings |
| `GET /seasons/{year}/progression` | Points after each round for the top drivers |
| `GET /sessions/{id}/overview`, `/drivers`, `/laps` | Session data (laps include track status) |
| `POST /sessions/{id}/compare`, `GET /sessions/{id}/telemetry/{driver}` | Driver comparison, telemetry |
| `GET /drivers/{code}/profile`, `/drivers/{code}/tracks` | Driver analytics |
| `GET /constructors/{team}/profile` | Team analytics |
| `GET /championships/{year}/drivers` and `/constructors` | Championship forecast |
| `GET /predictions/{year}` | Upcoming races |
| `GET /predictions/{year}/rounds/{n}` | Forecast for one race |
| `POST /predictions/{year}/rounds/{n}/snapshot` | Save a forecast snapshot |
| `GET /predictions/{year}/track-record?source=frozen\|replay` | Track record |
| `POST /strategy/simulate` | Strategy simulation |
| `GET /telemetry/sessions`, `/sessions/{id}/lap-comparison`, `/circuits/{id}/geometry` | Circuit Lab data |
| `POST /ingestion/jobs`, `GET /ingestion/jobs/{id}` | Run and poll an ingestion job |

Routers contain only request handling; computation lives in `analytics`, `ml` and `services`.

## 15. Module 10: Frontend

- **Routing and layout:** `App.jsx` (sidebar on desktop, bottom bar on phones; Circuit Lab is lazy-loaded so Three.js
  does not slow the other pages).
- **Data fetching:** every call is in `services/api.js`; pages use TanStack Query. `QueryState` shows
  loading/error/empty uniformly (a crash on disabled queries was fixed and tested).
- **Season state:** `hooks/useSeason.jsx` keeps the selected season across pages; `PageHeader` shows labelled
  **Race** and **Season** selectors.
- **Design ("Pit wall"):** dark theme, team colours from `utils/teams.js`, KPI tiles, bar rows, a 3D scene. Checked
  at 1600 px, 375 px and 320 px with no horizontal scroll and 44 px minimum tap targets.
- **Predictions page** (`Predictions.jsx`): KPI tiles (mode, rounds used, circuit history, model), podium cards,
  classification table, constructor bars, caveats, position heatmap (cell opacity = probability), and the
  `TrackRecord` panel with a calibration chart.
- **Race Explorer:** race sessions only; fetches laps per selected driver; shades safety car/VSC/red flag and marks
  pit stops.

## 16. Testing

- **Backend (pytest, `backend/tests`):** ingestion (idempotency, status not reset), pit-loss estimator, season
  metrics, telemetry (alignment and delta), simulation and evaluation maths, race model and forecast, snapshots
  (including the freeze rule), track record, API endpoints.
- **Frontend (Vitest, `frontend/src`):** pages, design/mobile helpers, track-record view, telemetry utilities,
  playback. Currently **74 tests pass** and `vite build` succeeds.
- Several bugs found by these tests were real (e.g. re-ingestion resetting status); the regression tests stay.

## 17. How to run it

**Backend**
```bash
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env        # leave DATABASE_URL unset for SQLite
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

**Get data (first time; needs internet, and an F1 account sign-in for FastF1 on first use).** The database and
cache are **not** in the repository, so a fresh clone must ingest first:
```bash
cd backend
.venv\Scripts\python scripts/ingest_season.py 2025 --sessions R,S,SQ,Q
.venv\Scripts\python scripts/ingest_season.py 2026 --sessions R,S,SQ,Q
.venv\Scripts\python scripts/ingest_season.py 2026 --sessions Q --telemetry --new-only
```
**Keep the running season up to date** after each race weekend:
```bash
.venv\Scripts\python scripts/ingest_season.py 2026 --sessions R,S,SQ,Q --new-only
```
**Tests:** `cd backend && python -m pytest` and `cd frontend && npm test`.
**Regenerate an evaluation:** e.g. `python -m scripts.run_rolling 2023 2024 2025 2026`.

## 18. Honest limitations

- Forecasts do not model weather, safety cars, strategy, first-lap incidents, grid penalties or pit-lane starts.
- The 2026 regulations are new, so settings tuned on 2023–2025 are untested on them.
- Before qualifying all upcoming races have the same forecast (circuit effect did not help).
- Strategy intervals cover lap-to-lap noise only; tyre-model coefficients are weakly identified.
- Circuit geometry is reconstructed from one lap's positions: approximate and flat.
- Telemetry is stored for selected qualifying sessions only; weather table is not populated.
- Replay track record is optimistic; the frozen track record is empty until the first snapshotted race is run.
- Championship tie-break is simplified.

## 19. Future work

- PostgreSQL with Alembic migrations and deployment (Docker Compose is a starting point).
- Scheduled automatic refresh after every race weekend.
- Weather and safety-car modelling; penalties from official data.
- More telemetry coverage; elevation data for the track.

---

## 20. Viva preparation: likely questions and answers

### A. Project overview
1. **What is the project about?** A dashboard that ingests real F1 data, analyses performance, simulates pit
   strategies and gives probabilistic forecasts for races and the championship.
2. **Why this topic?** F1 has rich, free, structured data; it lets us combine data engineering, statistics,
   backend and frontend in one realistic system.
3. **Who is the user?** A fan or analyst who wants more than raw results: probabilities, driver/team comparison and
   strategy what-ifs.
4. **What is the end-to-end flow?** FastF1 → ingestion → database → analytics/models → FastAPI → React.
5. **What is original in your work?** The honest-evaluation framework: pre-registered adoption rules, frozen
   forecast snapshots, calibration, and refusing to adopt models that failed.

### B. Data and ingestion
6. **Where does the data come from?** FastF1, which wraps official F1 timing data.
7. **Why a local database instead of calling FastF1 from the website?** Speed, reliability, and the browser must not
   depend on a slow external service; ingestion is separated from serving.
8. **What does idempotent mean here?** Re-running ingestion gives the same database without duplicates (get-or-create
   entities, replace a session's rows in one transaction).
9. **How do you handle missing or bad data?** Validation reports, nullable fields, lap classification, and
   robust statistics (medians, trimming).
10. **Why are circuit names aliased?** The same circuit appears under different names in different seasons; without
    merging, circuit history would be split.
11. **Why is telemetry down-sampled?** Full telemetry is huge; ~400 points per lap is enough for charts and 3D.
12. **What is the FastF1 cache?** A local copy of downloaded data so reruns are fast. It is 4 GB, so it is excluded
    from git.
13. **How do you update the live season?** `ingest_season.py 2026 --new-only` fetches only sessions not yet stored.
14. **What went wrong with re-ingestion once?** The schedule upsert reset loaded sessions to "not loaded"; fixed to
    create-only and covered by a regression test.

### C. Database
15. **Why SQLite? Why not PostgreSQL?** SQLite needs no setup for development. SQLAlchemy models are portable;
    `DATABASE_URL` switches to Postgres and a Compose file exists.
16. **Explain the schema.** Season → Event → Session → SessionEntry (driver in a session) → Laps / PitStops /
    Telemetry, with Drivers, Constructors and Circuits as reference tables.
17. **Which constraints keep data consistent?** Foreign keys and unique keys (e.g. one snapshot per year, round,
    mode).
18. **What is an ORM and why use it?** Maps tables to Python classes; avoids hand-written SQL and works across
    databases.
19. **Why no migrations yet?** Development used `create_all`; Alembic is listed as future work.

### D. Analytics
20. **How do you measure driver pace fairly?** Median of clean laps (valid, within 107% of own median), as a % of
    the field median in the same race.
21. **Why a percentage?** Circuits have different lap lengths; percentages are comparable.
22. **Why the teammate gap?** Same car, so the difference is the driver.
23. **Why median, not mean?** Robust to outliers like spins and traffic.
24. **How do you estimate pit-stop loss?** In-lap + out-lap minus two local clean laps, median over stops, with
    exclusions for neutralised and wet stops and a 22 s fallback.
25. **Why was the naive pit-loss estimate wrong?** Safety cars and VSC make a stop look cheap or costly; it gave
    30–49 s in about a sixth of races.
26. **What is the tyre model?** Quadratic in tyre age plus a lap-number fuel proxy, per compound.
27. **Why a quadratic?** Degradation often accelerates late in a stint; it is still simple and interpretable.
28. **What is the fuel proxy?** Lap number stands in for fuel load, which falls during the race. It is an
    assumption, not a measurement.
29. **What are the weaknesses of the tyre model?** Age, age² and lap number are correlated, so single coefficients
    are unreliable; only the combined effect is.

### E. Forecasting and statistics
30. **What is Plackett–Luce?** A model for rankings: each item has a strength and is picked first with probability
    proportional to strength, then the next from the remainder, and so on.
31. **What is the Gumbel trick?** Adding Gumbel noise to log-strengths and sorting gives exactly a Plackett–Luce
    sample, which is fast to vectorise.
32. **Why Monte Carlo?** It gives a full probability distribution and keeps driver, constructor and championship
    results consistent.
33. **How many simulations and why?** 10,000–20,000; enough that Monte-Carlo error is small (about ±0.3 percentage
    points on a 50% event).
34. **How is strength computed?** Points per race this season, shrunk toward the field average, then raised to a
    sharpening power.
35. **What is shrinkage?** Pulling small-sample estimates toward the average to avoid over-reacting to a few races.
36. **Why sharpening?** Unsharpened, the model under-estimated how dominant the best drivers are; α = 2.5 fixed
    most of that.
37. **How was α chosen without cheating?** Expanding-window validation: choose on earlier seasons, test on the
    next; and a cross-season check.
38. **How do you model retirements?** Per-driver and per-team DNF rates from earlier races, shrunk to the average;
    adopted because retirement log-loss improved from 0.449 to 0.393.
39. **How does the post-qualifying model use the grid?** `strength = form^1.5 × grid^−2.0`; better grid, higher
    strength.
40. **Why do upcoming races look identical before qualifying?** Same input data; a circuit effect was tested and did
    not help, so it was rejected. Qualifying breaks the tie.
41. **What does "expected position" mean?** The average finishing position over simulations, with a retirement
    counted as last. It is not the single most likely order.
42. **Can the model predict the winner with certainty?** No, and it says so: it outputs probabilities.
43. **What does the championship forecast do differently?** Simulates all remaining races, adds points to current
    totals, and counts how often each driver ends first.
44. **What does the model ignore?** Weather, safety cars, strategy, first-lap crashes, grid penalties.

### F. Evaluation and honesty
45. **How do you know the model is any good?** Backtests against a uniform baseline and simpler baselines
    (championship order, last race result), with intervals.
46. **What is log loss?** Average negative log of the probability given to what actually happened. Lower is better;
    it punishes confident mistakes.
47. **What is Brier score?** Mean squared difference between predicted probability and outcome (0 or 1).
48. **What is calibration?** Of events predicted at about 30%, roughly 30% should occur. We tabulate this per bin.
49. **What is a forward-chaining backtest?** Each race is predicted using only earlier races; no future leakage.
50. **What is a bootstrap confidence interval?** Resample races with replacement many times to see the spread of
    the average difference between two models.
51. **What is a pre-registered rule and why?** The adoption criterion is written before running the test, so we
    cannot rationalise a result afterwards.
52. **Name a model you rejected.** The richer pace-plus-qualifying strength model: its ordering was better but its
    probability improvements did not clear zero, so by our own rule it was not adopted. The circuit effect was also
    rejected.
53. **Is the replay track record trustworthy?** Only partly: parameters were tuned on those races, so it is
    optimistic. That is why the frozen track record exists.
54. **What is a frozen snapshot?** A forecast saved before the race and made un-overwritable once the race is run.
55. **How many races have been scored with frozen forecasts?** None yet; the first will be after the Mexico City
    Grand Prix (1 Nov 2026).
56. **What is Spearman correlation?** Rank correlation between predicted and actual finishing order (1 = perfect).

### G. Strategy Lab
57. **How does the strategy simulator work?** Predict each lap's time from the tyre model for both strategies,
    add pit-loss per stop, and compare totals.
58. **Why compare model-to-model instead of to the real clock?** The same bias appears in both and largely cancels.
59. **What does the shaded band mean?** A 90% interval from resampling lap-to-lap residuals; it excludes traffic,
    safety cars and weather.
60. **What rules are checked?** At least two different dry compounds in a dry race, stints of at least 3 laps, at
    most 4 stops, and pit laps that increase and stay inside the race.

### H. Telemetry and 3D
61. **How do you draw the track without map data?** Smooth the x/y position samples of one lap into a closed loop.
62. **Why is the geometry only approximate?** One lap, GPS-like noise, no elevation, not surveyed.
63. **How do you compute the time delta between two drivers?** Rescale both laps to a common distance, resample by
    distance, and take the difference in elapsed time at each point.
64. **What was the earlier error and how was it fixed?** Distances integrated from speed differ slightly per lap,
    causing up to 0.4 s error; normalising distance and scaling to the official lap time fixed it.
65. **Why lazy-load the 3D page?** Three.js is large; lazy loading keeps other pages fast.

### I. Backend, API and frontend
66. **Why FastAPI?** Type-checked requests with Pydantic, async-capable, automatic docs.
67. **How is business logic separated from the API?** Routers only handle HTTP; pure functions in
    `analytics`/`ml`/`strategy`, glue in `services`.
68. **How does the frontend get data?** `services/api.js` plus TanStack Query hooks, which cache and handle loading
    and error states.
69. **Why React Query instead of Redux?** The state is mostly server data; React Query handles that directly.
70. **How is the UI responsive?** CSS grid with `minmax`, bottom nav on phones, tested at 320/375/1600 px.
71. **How is accessibility handled?** Labelled controls, `role="note"` banners, aria-labels on heatmap cells, 44 px
    tap targets.
72. **How do you handle CORS?** The backend allows the origins listed in `CORS_ORIGINS`.
73. **Why only JavaScript, not TypeScript?** A project requirement; PropTypes were not needed because the API shapes
    are covered by tests.

### J. Testing and quality
74. **How is the code tested?** pytest for backend logic and API, Vitest/Testing Library for frontend (74 frontend
    tests pass).
75. **Give an example of a bug the tests caught.** Re-ingestion reset session status; blank page when a disabled
    query had no data.
76. **Why are most functions "pure"?** No hidden I/O means they are deterministic and easy to unit-test.

### K. Limitations, ethics and future work
77. **What are the biggest limitations?** No weather/safety-car/penalty modelling; new 2026 regulations; approximate
    geometry; replay is optimistic.
78. **Is this betting advice?** No, and the page says probabilities are estimates, not guarantees.
79. **What would you do with more time?** Postgres and Alembic, deployment, scheduled refresh, weather and
    safety-car modelling, more telemetry.
80. **How would you deploy it?** Docker Compose (Postgres + backend), static frontend build served by any web host,
    a scheduled job for new-race ingestion.
81. **How would you scale it?** Postgres, caching of forecasts, background workers for ingestion, CDN for the
    frontend.
82. **Is the data licensed?** FastF1 uses publicly available timing data for non-commercial/educational use; the
    project is for study.

### L. Tricky "gotcha" questions
83. **"Your model says a driver has 27% to win. He didn't. Was it wrong?"** No. A 27% event fails 73% of the time.
    Only many forecasts together, via calibration, can judge it.
84. **"Why not use machine learning like a neural network?"** With about 20–24 races a season there is too little
    data; simple, shrunk, interpretable models were evaluated honestly, and the richer one did not beat the baseline.
85. **"Isn't tuning on past seasons cheating?"** Not when parameters are chosen only on earlier data and tested on
    later; the grid exponent was chosen on all seasons, and we label that replay as optimistic.
86. **"Why trust the pit-loss number?"** It was validated on 88 races, uses a median with exclusions, and falls back
    to a default with a visible note when data is messy.
87. **"What does the heatmap show?"** For each driver, the probability of finishing in each position; each row sums
    to 100% minus the retirement chance.
