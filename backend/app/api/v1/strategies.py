from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics.pit_stop_analysis import estimate_pit_loss_detail
from app.analytics.driver_metrics import clean_laps
from app.analytics.tire_degradation import InsufficientDataError, fit_degradation
from app.core.database import get_db
from app.models import database_models as m
from app.models.schemas import StrategyRequest, StrategyResponse
from app.services.frames import session_laps_frame
from app.strategy.simulator import MODEL_VERSION, simulate_strategy

def _stop_under_neutralisation(driver_laps, pit_laps) -> bool:
    """True if any of the driver's stops fell on a lap run under SC/VSC/red flag (judged from track status,
    because the stored validity reason of a pit lap hides that it was also neutralised)."""
    rows = driver_laps[driver_laps["lap_number"].isin(pit_laps)]
    return bool(rows["neutralised"].any() or rows["track_status"].astype(str).str.contains("[4567]", regex=True).any())


router = APIRouter(prefix="/strategy", tags=["strategy"])


def actual_strategy(driver_laps) -> tuple[list[str], list[int], int]:
    d = driver_laps.dropna(subset=["stint", "compound"]).sort_values("lap_number")
    compounds, pits = [], []
    for _, g in d.groupby("stint", sort=True):
        compounds.append(str(g["compound"].iloc[0]).upper())
        pits.append(int(g["lap_number"].max()))
    return compounds, pits[:-1], int(driver_laps["lap_number"].max())


@router.post("/simulate", response_model=StrategyResponse)
def simulate(body: StrategyRequest, db: Session = Depends(get_db)):
    if db.get(m.SessionRow, body.session_id) is None:
        raise HTTPException(404, "Session not found")
    laps = session_laps_frame(db, body.session_id)
    code = body.driver_code.upper()
    mine = laps[laps["driver"] == code]
    if mine.empty:
        raise HTTPException(404, f"No laps for driver {code}")

    try:
        model = fit_degradation(clean_laps(laps))
    except InsufficientDataError as exc:
        raise HTTPException(422, str(exc))
    pit = estimate_pit_loss_detail(laps)
    pit_loss, warn = pit.value, pit.warning
    comps, pits, total = actual_strategy(mine)
    warns = [warn] if warn else []
    bounds = [0, *pits, total]
    if any(b - a < 3 for a, b in zip(bounds, bounds[1:])) or _stop_under_neutralisation(mine, pits):
        warns.append("The driver's actual strategy includes a very short stint or a stop under SC/VSC/red flag; "
                     "the baseline is unrepresentative of a normal race and deltas should not be trusted.")
    res = simulate_strategy(
        model, total, pit_loss, (comps, pits), (body.stint_compounds, body.pit_laps),
        runs=body.simulation_runs, extra_warnings=warns,
    )
    return StrategyResponse(
        estimated_race_time_seconds=res.estimated_race_time_s, baseline_delta_seconds=res.baseline_delta_s,
        uncertainty_interval_seconds=res.uncertainty_interval_s, stints=res.stints,
        constraint_violations=res.constraint_violations, warnings=res.warnings,
        model_version=MODEL_VERSION, pit_loss_seconds=pit_loss, pit_loss_source=pit.source,
        pit_loss_stops=pit.n_stops, actual_stints=res.actual_stints, profile=res.profile,
        generated_at=datetime.now(timezone.utc),
    )
