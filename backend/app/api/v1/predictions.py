from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml.race_forecast import ForecastError
from app.services import forecast_service as fs
from app.services import track_record_service as tr

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, fs.ForecastNotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, fs.RaceAlreadyRun):
        return HTTPException(409, str(exc))
    return HTTPException(422, str(exc))              # ForecastError


@router.get("/{year}")
def upcoming(year: int, db: Session = Depends(get_db)):
    """Rounds that have not been raced yet, with what data a forecast for each can use."""
    try:
        return fs.upcoming(db, year)
    except fs.ForecastNotFound as exc:
        raise _http(exc)


@router.get("/{year}/rounds/{round_number}")
def race_forecast(year: int, round_number: int, n_sims: int = Query(20000, ge=2000, le=50000), seed: int = 0,
                  db: Session = Depends(get_db)):
    try:
        return fs.build_forecast(db, year, round_number, n_sims, seed)
    except (fs.ForecastNotFound, fs.RaceAlreadyRun, ForecastError) as exc:
        raise _http(exc)


@router.get("/{year}/track-record")
def track_record(year: int, source: str = Query("frozen", pattern="^(frozen|replay)$"), db: Session = Depends(get_db)):
    """How forecasts compared with results. `frozen`: snapshots saved before their race. `replay`: past races
    forecast again afterwards (not frozen, optimistic; labelled as such in the response)."""
    try:
        fs.get_season(db, year)
    except fs.ForecastNotFound as exc:
        raise _http(exc)
    if source == "frozen":
        return tr.frozen_track_record(db, year)
    return tr.replay_track_record(db, year)


@router.post("/{year}/rounds/{round_number}/snapshot", status_code=201)
def snapshot(year: int, round_number: int, db: Session = Depends(get_db)):
    """Save the current forecast as this race's snapshot (replacing an earlier one of the same mode). Only possible
    before the race result exists; after that the snapshot is frozen."""
    try:
        snap = fs.save_snapshot(db, fs.build_forecast(db, year, round_number))
    except (fs.ForecastNotFound, fs.RaceAlreadyRun, ForecastError) as exc:
        raise _http(exc)
    return {"year": year, "round": round_number, "mode": snap.mode, "model_version": snap.model_version,
            "saved_at": snap.updated_at.isoformat()}
