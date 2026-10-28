from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import database_models as m

router = APIRouter(tags=["seasons"])


@router.get("/seasons")
def list_seasons(db: Session = Depends(get_db)):
    return [{"year": s.year, "status": s.status} for s in db.scalars(select(m.Season).order_by(m.Season.year.desc()))]


@router.get("/events")
def list_events(season: int, db: Session = Depends(get_db)):
    s = db.scalar(select(m.Season).where(m.Season.year == season))
    if s is None:
        raise HTTPException(404, f"Season {season} has not been ingested")
    rows = db.execute(
        select(m.Event, m.Circuit.name).outerjoin(m.Circuit).where(m.Event.season_id == s.id).order_by(m.Event.round_number)
    ).all()
    out = []
    for ev, circuit in rows:
        sessions = db.scalars(select(m.SessionRow).where(m.SessionRow.event_id == ev.id)).all()
        out.append({
            "event_id": ev.id, "round": ev.round_number, "name": ev.event_name, "circuit": circuit,
            "sessions": [{"session_id": x.id, "type": x.session_type, "status": x.status} for x in sessions],
        })
    return out


@router.get("/seasons/{year}/standings")
def standings(year: int, db: Session = Depends(get_db)):
    """Computed from ingested race sessions' points (so it reflects only loaded rounds)."""
    s = db.scalar(select(m.Season).where(m.Season.year == year))
    if s is None:
        raise HTTPException(404, f"Season {year} has not been ingested")
    entries = db.execute(
        select(m.SessionEntry, m.Driver.code, m.Driver.full_name, m.Constructor.name, m.SessionRow.session_type)
        .join(m.SessionRow, m.SessionEntry.session_id == m.SessionRow.id)
        .join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .outerjoin(m.Constructor, m.SessionEntry.constructor_id == m.Constructor.id)
        .where(m.Event.season_id == s.id, m.SessionRow.session_type.in_(["R", "S"]), m.SessionRow.status == "loaded")
    ).all()
    d: dict[str, dict] = {}
    t: dict[str, float] = {}
    for e, code, name, team, stype in entries:
        row = d.setdefault(code, {"driver": code, "name": name, "constructor": team, "points": 0.0, "wins": 0})
        row["points"] += e.points or 0.0
        row["constructor"] = team
        row["wins"] += 1 if (stype == "R" and e.finish_position == 1) else 0  # sprint wins are not GP wins
        if team:
            t[team] = t.get(team, 0.0) + (e.points or 0.0)
    drv = sorted(d.values(), key=lambda r: (-r["points"], -r["wins"]))
    con = sorted(({"constructor": k, "points": v} for k, v in t.items()), key=lambda r: -r["points"])
    for i, r in enumerate(drv, 1):
        r["position"] = i
    for i, r in enumerate(con, 1):
        r["position"] = i
    return {"year": year, "drivers": drv, "constructors": con,
            "note": "Computed from ingested sessions only; sprint points included when sprints were ingested."}
