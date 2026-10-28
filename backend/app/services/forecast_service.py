"""Building, saving and listing race forecasts (shared by the API, scripts and the ingestion hook)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml import features
from app.ml.race_forecast import ForecastError, forecast_race
from app.models import database_models as m
from app.services import frames


class ForecastNotFound(Exception):
    """Unknown season or round."""


class RaceAlreadyRun(Exception):
    """The race result already exists: forecasts (and snapshots) are only for upcoming races."""


def get_season(db: Session, year: int) -> m.Season:
    s = db.scalar(select(m.Season).where(m.Season.year == year))
    if s is None:
        raise ForecastNotFound(f"Season {year} has not been ingested")
    return s


def event_rows(db: Session, season: m.Season):
    """(event, circuit name, race status, qualifying status) for every round, in order."""
    events = db.execute(
        select(m.Event, m.Circuit.name).outerjoin(m.Circuit, m.Event.circuit_id == m.Circuit.id)
        .where(m.Event.season_id == season.id).order_by(m.Event.round_number)
    ).all()
    status = {(ev_id, t): st for ev_id, t, st in db.execute(
        select(m.SessionRow.event_id, m.SessionRow.session_type, m.SessionRow.status)
        .join(m.Event, m.SessionRow.event_id == m.Event.id).where(m.Event.season_id == season.id))}
    return [(e, c, status.get((e.id, "R")), status.get((e.id, "Q"))) for e, c in events]


def history_seasons(db: Session, circuit_id: int | None, before_year: int) -> int:
    if circuit_id is None:
        return 0
    return db.scalar(
        select(func.count(func.distinct(m.Season.year))).select_from(m.Event)
        .join(m.Season, m.Event.season_id == m.Season.id).join(m.SessionRow, m.SessionRow.event_id == m.Event.id)
        .where(m.Event.circuit_id == circuit_id, m.Season.year < before_year, m.SessionRow.session_type == "R",
               m.SessionRow.status == "loaded")) or 0


def upcoming(db: Session, year: int) -> dict:
    season = get_season(db, year)
    rows = event_rows(db, season)
    completed = sum(1 for _, _, r, _ in rows if r == "loaded")
    out = []
    for e, circuit, race, quali in rows:
        if race == "loaded":
            continue
        out.append({
            "round": e.round_number, "event": e.event_name, "circuit": circuit,
            "date": e.event_date.date().isoformat() if e.event_date else None,
            "qualifying_available": quali == "loaded",
            "circuit_history_seasons": history_seasons(db, e.circuit_id, year),
            "forecastable": completed > 0,
        })
    return {"year": year, "completed_rounds": completed, "upcoming": out}


def build_forecast(db: Session, year: int, round_number: int, n_sims: int = 20000, seed: int = 0) -> dict:
    """Forecast an upcoming race from everything ingested so far. Raises ForecastNotFound, RaceAlreadyRun or
    ForecastError (all with user-safe messages)."""
    season = get_season(db, year)
    match = next((r for r in event_rows(db, season) if r[0].round_number == round_number), None)
    if match is None:
        raise ForecastNotFound(f"Season {year} has no round {round_number}")
    event, circuit, race_status, quali_status = match
    if race_status == "loaded":
        raise RaceAlreadyRun("That race has already been run; forecasts are only made for upcoming races.")

    history = frames.season_results_frame(db, year)
    history = history[history["round"] < round_number]
    names = dict(db.execute(select(m.Driver.code, m.Driver.full_name)).all())
    quali = None
    if quali_status == "loaded":
        q = frames.entries_frame(db, year, types=("Q",))
        q = q[(q["round"] == round_number) & q["finish"].notna()]
        quali = {r.driver: (float(r.finish), r.team) for r in q.itertuples()}
    result = forecast_race(history, year, names=names, n_sims=n_sims, seed=seed,
                           dnf_history=features.dnf_history(db), quali=quali)
    result["race"] = {
        "year": year, "round": round_number, "event": event.event_name, "circuit": circuit,
        "date": event.event_date.date().isoformat() if event.event_date else None,
        "qualifying_available": quali_status == "loaded",
        "circuit_history_seasons": history_seasons(db, event.circuit_id, year),
    }
    return result


def save_snapshot(db: Session, forecast: dict) -> m.RaceForecastSnapshot:
    """Store `forecast` as the snapshot for its (season, round, mode). Replaces an earlier snapshot of the same mode
    while the race has not been run; refuses once the race result exists, which is what freezes it."""
    year, rnd = forecast["race"]["year"], forecast["race"]["round"]
    season = get_season(db, year)
    match = next((r for r in event_rows(db, season) if r[0].round_number == rnd), None)
    if match is None:
        raise ForecastNotFound(f"Season {year} has no round {rnd}")
    if match[2] == "loaded":
        raise RaceAlreadyRun("The race has been run; its snapshot is frozen and cannot change.")
    snap = db.scalar(select(m.RaceForecastSnapshot).where(
        m.RaceForecastSnapshot.year == year, m.RaceForecastSnapshot.round_number == rnd,
        m.RaceForecastSnapshot.mode == forecast["mode"]))
    fields = dict(model_version=forecast["model_version"], as_of_round=forecast["as_of_round"],
                  n_simulations=forecast["n_simulations"], seed=forecast["seed"],
                  generated_at=datetime.fromisoformat(forecast["generated_at"]).replace(tzinfo=None), payload=forecast)
    if snap is None:
        snap = m.RaceForecastSnapshot(year=year, round_number=rnd, mode=forecast["mode"], **fields)
        db.add(snap)
    else:
        for k, v in fields.items():
            setattr(snap, k, v)
    db.commit()
    return snap


def snapshot_upcoming(db: Session, year: int, n_sims: int = 20000, seed: int = 0) -> list[dict]:
    """Snapshot every upcoming race that can be forecast. Returns a summary per race (no payloads)."""
    out = []
    for u in upcoming(db, year)["upcoming"]:
        if not u["forecastable"]:
            continue
        try:
            snap = save_snapshot(db, build_forecast(db, year, u["round"], n_sims, seed))
        except (ForecastError, RaceAlreadyRun, ForecastNotFound) as exc:
            out.append({"round": u["round"], "event": u["event"], "status": "skipped", "reason": str(exc)})
            continue
        out.append({"round": u["round"], "event": u["event"], "status": "saved", "mode": snap.mode,
                    "model_version": snap.model_version})
    return out
