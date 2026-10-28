"""Track record: how forecasts compared with what happened.

Two sources, kept strictly apart:
- frozen: snapshots saved BEFORE their race and never changed (see forecast_service.save_snapshot). The honest test.
- replay: past races forecast again afterwards, using only data that existed before each race and the current model.
  NOT frozen, and the model's settings were chosen using these races, so replay scores are optimistic.
"""

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.race_forecast import MIN_GRID_SHARE, ForecastError, forecast_race
from app.ml.track_record import TARGETS, calibration_table, score_forecast, summarise
from app.models import database_models as m
from app.services import frames

FROZEN_NOTE = "Forecasts saved before each race and never changed afterwards: the honest test of the model."
REPLAY_NOTE = ("Retrospective replay, NOT frozen: each race is forecast again afterwards using only the data that existed "
               "before it, with today's model. The model's settings were chosen using these same races, so these scores "
               "are optimistic. Frozen forecasts are the real test.")
MIN_PRIOR_ROUNDS = 4          # same warm-up as the backtests
REPLAY_SIMS = 4000

_REPLAY_CACHE: dict[tuple, dict] = {}


def clear_replay_cache() -> None:
    _REPLAY_CACHE.clear()


def _actuals(db: Session, year: int):
    """round -> {driver: classified finish}, plus round -> event name, for loaded races."""
    ent = frames.entries_frame(db, year, types=("R",))
    ent = ent[ent["finish"].notna()]
    actual = {int(r): dict(zip(g["driver"], g["finish"].astype(int))) for r, g in ent.groupby("round")}
    events = ent.drop_duplicates("round").set_index("round")["event"].to_dict()
    return actual, {int(k): v for k, v in events.items()}


def _assemble(source: str, year: int, note: str, items: list[tuple[dict, dict, dict]]) -> dict:
    """items: (meta, score, pairs). Builds the response: per-race rows, per-mode summary and calibration."""
    items = sorted(items, key=lambda it: (it[0]["round"], it[0]["mode"]))
    modes = sorted({meta["mode"] for meta, _, _ in items})
    summary, calibration = {}, {}
    for mode in modes:
        sel = [(s, p) for meta, s, p in items if meta["mode"] == mode]
        summary[mode] = summarise([s for s, _ in sel])
        calibration[mode] = {t: calibration_table([pr for _, p in sel for pr in p[t]]) for t in TARGETS}
    return {"year": year, "source": source, "note": note, "modes": modes,
            "races": [{**meta, **score} for meta, score, _ in items], "summary": summary, "calibration": calibration}


def frozen_track_record(db: Session, year: int) -> dict:
    actual, events = _actuals(db, year)
    snaps = db.scalars(select(m.RaceForecastSnapshot).where(m.RaceForecastSnapshot.year == year)).all()
    items = []
    pending = []
    for s in snaps:
        if s.round_number not in actual:
            pending.append({"round": s.round_number, "mode": s.mode, "saved_at": s.updated_at.isoformat(),
                            "event": s.payload.get("race", {}).get("event")})
            continue
        scored = score_forecast(s.payload["drivers"], actual[s.round_number])
        if scored is None:
            continue
        meta = {"round": s.round_number, "event": events.get(s.round_number), "mode": s.mode,
                "model_version": s.model_version, "forecast_saved_at": s.updated_at.isoformat()}
        items.append((meta, *scored))
    out = _assemble("frozen", year, FROZEN_NOTE, items)
    out["pending"] = sorted(pending, key=lambda p: (p["round"], p["mode"]))
    return out


def replay_track_record(db: Session, year: int, n_sims: int = REPLAY_SIMS) -> dict:
    n_loaded = db.scalar(
        select(func.count()).select_from(m.SessionRow).join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Season, m.Event.season_id == m.Season.id)
        .where(m.Season.year == year, m.SessionRow.session_type == "R", m.SessionRow.status == "loaded")) or 0
    key = (year, n_loaded, n_sims)
    if key in _REPLAY_CACHE:
        return _REPLAY_CACHE[key]

    actual, events = _actuals(db, year)
    results = frames.season_results_frame(db, year)
    ent_all = frames.entries_frame(db, None, types=("R", "Q"))
    race_all = ent_all[ent_all["stype"] == "R"][["year", "round", "driver", "team", "status"]].copy()
    from app.analytics.season_metrics import is_dnf
    race_all["dnf"] = race_all["status"].map(is_dnf).astype(bool)
    race_all["team"] = race_all["team"].fillna("Unknown")
    quali_year = ent_all[(ent_all["stype"] == "Q") & (ent_all["year"] == year)]

    items = []
    for rnd in sorted(actual):
        if rnd <= MIN_PRIOR_ROUNDS:
            continue
        history = results[results["round"] < rnd]
        dnf_hist = race_all[(race_all["year"] < year) | ((race_all["year"] == year) & (race_all["round"] < rnd))]
        q = quali_year[(quali_year["round"] == rnd) & quali_year["finish"].notna()]
        quali = {r.driver: (float(r.finish), r.team) for r in q.itertuples()}
        variants = [("pre-qualifying", None)]
        if len(quali) >= MIN_GRID_SHARE * len(actual[rnd]):
            variants.append(("post-qualifying", quali))
        for mode, qd in variants:
            try:
                f = forecast_race(history, year, n_sims=n_sims, dnf_history=dnf_hist[["driver", "team", "dnf"]], quali=qd)
            except ForecastError:
                continue
            scored = score_forecast(f["drivers"], actual[rnd])
            if scored is None or f["mode"] != mode:
                continue
            meta = {"round": rnd, "event": events.get(rnd), "mode": mode, "model_version": f["model_version"],
                    "forecast_saved_at": None}
            items.append((meta, *scored))
    out = _assemble("replay", year, REPLAY_NOTE, items)
    out["pending"] = []
    _REPLAY_CACHE[key] = out
    return out
