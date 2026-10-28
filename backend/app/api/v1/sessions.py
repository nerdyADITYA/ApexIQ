import math

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import driver_metrics
from app.core.database import get_db
from app.models import database_models as m
from app.services.frames import session_laps_frame

router = APIRouter(tags=["sessions"])


def _session_or_404(db: Session, session_id: int) -> m.SessionRow:
    s = db.get(m.SessionRow, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    return s


def _clean(v):
    """JSON cannot carry NaN; missing stays null, never 0."""
    return None if isinstance(v, float) and math.isnan(v) else v


@router.get("/sessions/{session_id}/overview")
def overview(session_id: int, db: Session = Depends(get_db)):
    s = _session_or_404(db, session_id)
    ev = s.event
    return {
        "session_id": s.id, "type": s.session_type, "status": s.status, "event": ev.event_name,
        "round": ev.round_number, "completeness": s.completeness,
    }


@router.get("/sessions/{session_id}/drivers")
def session_drivers(session_id: int, db: Session = Depends(get_db)):
    _session_or_404(db, session_id)
    rows = db.execute(
        select(m.SessionEntry, m.Driver, m.Constructor.name)
        .join(m.Driver).outerjoin(m.Constructor).where(m.SessionEntry.session_id == session_id)
        .order_by(m.SessionEntry.finish_position.is_(None), m.SessionEntry.finish_position)
    ).all()
    return [{"driver_id": d.id, "code": d.code, "name": d.full_name, "constructor": team,
             "grid": e.grid_position, "finish": e.finish_position, "points": e.points, "status": e.status}
            for e, d, team in rows]


@router.get("/sessions/{session_id}/laps")
def session_laps(
    session_id: int, driver: str | None = None, valid_only: bool = False,
    limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), db: Session = Depends(get_db),
):
    _session_or_404(db, session_id)
    df = session_laps_frame(db, session_id)
    if driver:
        df = df[df["driver"] == driver.upper()]
    if valid_only:
        df = df[df["is_valid"]]
    df = df.sort_values(["driver", "lap_number"])
    page = df.iloc[offset: offset + limit].astype(object).where(df.notna(), None)
    return {"total": int(len(df)), "limit": limit, "offset": offset,
            "units": {"lap_time_s": "seconds", "sectors": "seconds"},
            "laps": page.to_dict(orient="records")}


class CompareRequest(BaseModel):
    drivers: list[str] = Field(min_length=2, max_length=6)
    reference: str | None = None


@router.post("/sessions/{session_id}/compare")
def compare(session_id: int, body: CompareRequest, db: Session = Depends(get_db)):
    _session_or_404(db, session_id)
    df = session_laps_frame(db, session_id)
    codes = [c.upper() for c in body.drivers]
    df = df[df["driver"].isin(codes)]
    if df.empty:
        raise HTTPException(404, "No laps for requested drivers")
    ref = (body.reference or codes[0]).upper()
    pace = driver_metrics.pace_summary(df)
    try:
        sectors = driver_metrics.sector_deltas(df, ref)
    except KeyError as exc:
        raise HTTPException(422, str(exc))
    to_rec = lambda frame: [{k: _clean(v) for k, v in r.items()} for r in frame.to_dict("records")]  # noqa: E731
    return {"reference": ref, "pace": to_rec(pace), "sector_deltas_vs_reference": to_rec(sectors),
            "notes": ["Negative sector delta = faster than the reference.",
                      "Medians use valid laps within 107% of each driver's median; see excluded_laps."]}


@router.get("/sessions/{session_id}/telemetry/{driver_code}")
def telemetry(session_id: int, driver_code: str, db: Session = Depends(get_db)):
    _session_or_404(db, session_id)
    row = db.execute(
        select(m.Lap, m.SessionEntry).join(m.SessionEntry).join(m.Driver)
        .where(m.SessionEntry.session_id == session_id, m.Driver.code == driver_code.upper())
        .where(m.Lap.id.in_(select(m.TelemetryPoint.lap_id).distinct()))
    ).first()
    if row is None:
        raise HTTPException(404, "No telemetry stored for this driver/session")
    lap = row[0]
    pts = db.scalars(select(m.TelemetryPoint).where(m.TelemetryPoint.lap_id == lap.id).order_by(m.TelemetryPoint.sample_index)).all()
    return {
        "driver": driver_code.upper(), "lap_number": lap.lap_number,
        "lap_time_seconds": None if lap.lap_time_ms is None else lap.lap_time_ms / 1000,
        "has_position": any(p.x is not None for p in pts),
        "telemetry": [{"time_seconds": None if p.time_ms is None else p.time_ms / 1000, "distance_m": p.distance_m,
                       "x": p.x, "y": p.y, "speed_kph": p.speed_kph, "throttle": p.throttle,
                       "brake": p.brake, "gear": p.gear, "rpm": p.rpm} for p in pts],
    }
