from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import season_metrics as sm
from app.core.database import get_db
from app.models import database_models as m
from app.services import frames

router = APIRouter(tags=["analytics"])


def _split(db: Session, year: int):
    ent = frames.entries_frame(db, year, types=("R", "Q", "S"))
    if ent.empty:
        raise HTTPException(404, f"No ingested sessions for season {year}")
    race, quali, sprint = (ent[ent["stype"] == t] for t in ("R", "Q", "S"))
    sprint_pts = {(int(r.round), r.driver): float(r.points or 0.0) for r in sprint.itertuples()}
    return race, quali, sprint_pts


@router.get("/drivers/{code}/profile")
def driver_profile(code: str, season: int, db: Session = Depends(get_db)):
    race, quali, sprint_pts = _split(db, season)
    laps = frames.season_laps_frame(db, season, "R")
    try:
        return sm.driver_profile(code.upper(), race, quali, laps, sprint_pts) | {"season": season}
    except KeyError:
        raise HTTPException(404, f"Driver {code.upper()} has no ingested races in {season}")


@router.get("/drivers/{code}/tracks")
def driver_tracks(code: str, db: Session = Depends(get_db)):
    """Performance by circuit across every ingested season."""
    ent = frames.entries_frame(db, None, types=("R", "Q"))
    race, quali = ent[ent["stype"] == "R"], ent[ent["stype"] == "Q"]
    rows = sm.circuit_history(code.upper(), race, quali)
    if not rows:
        raise HTTPException(404, f"No ingested races for driver {code.upper()}")
    return {"driver": code.upper(), "circuits": rows,
            "notes": ["Small samples: most circuits have 1 to 2 starts here, so averages are anecdotal.",
                      "Compare across years with care: cars and regulations change."]}


@router.get("/constructors/{team}/profile")
def constructor_profile(team: str, season: int, db: Session = Depends(get_db)):
    race, quali, sprint_pts = _split(db, season)
    laps = frames.season_laps_frame(db, season, "R")
    pit = frames.pit_frame(db, season)
    try:
        return sm.constructor_profile(team, race, quali, laps, pit, sprint_pts) | {"season": season}
    except KeyError:
        raise HTTPException(404, f"Constructor {team!r} has no ingested races in {season}")


@router.get("/seasons/{year}/progression")
def season_progression(year: int, top: int = 6, db: Session = Depends(get_db)):
    """Cumulative points (race + sprint) after each ingested round for the current top drivers."""
    if not 1 <= top <= 20:
        raise HTTPException(422, "top must be between 1 and 20")
    res = frames.season_results_frame(db, year)
    if res.empty:
        raise HTTPException(404, f"No ingested races for season {year}")
    res = res.assign(points=res["race_points"] + res["sprint_points"])
    wide = res.pivot_table(index="round", columns="driver", values="points", aggfunc="sum").fillna(0.0).sort_index()
    cum = wide.cumsum()
    leaders = cum.iloc[-1].sort_values(ascending=False).head(top).index
    team = res.sort_values("round").groupby("driver")["team"].last()
    return {"year": year, "rounds": [int(r) for r in cum.index],
            "series": [{"driver": d, "team": None if d not in team or team[d] is None else str(team[d]),
                        "points": [float(v) for v in cum[d]]} for d in leaders]}
