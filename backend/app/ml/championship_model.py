"""Baseline championship forecast: points-per-race form -> Plackett-Luce strengths.

Model `baseline-points-form-v1`: strength_i = (points_i / races_run + prior) with
shrinkage toward the field mean. Uses only results already ingested for rounds
before the forecast date, so there is no future-information leakage.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.simulation import MODEL_VERSION as SIM_VERSION, simulate_championship
from app.models import database_models as m

PRIOR_POINTS_PER_RACE = 2.0
# Sharpening exponent from the 2024 expanding-window backtest (chosen alpha settled at 2.5; see
# docs/evaluation-report.md). Selected on 2024 only, so treat it as provisional.
SHARPEN = 2.5
MODEL_VERSION = f"points-form-sharpen{SHARPEN}-v2+{SIM_VERSION}"


def forecast(db: Session, year: int, n_sims: int = 10000, seed: int = 0) -> dict:
    season = db.scalar(select(m.Season).where(m.Season.year == year))
    if season is None:
        raise LookupError(f"Season {year} not ingested")
    races = db.execute(
        select(m.SessionRow, m.Event).join(m.Event).where(m.Event.season_id == season.id, m.SessionRow.session_type == "R")
    ).all()
    done = [s.id for s, _ in races if s.status == "loaded"]
    if not done:
        raise LookupError("No completed races ingested for this season")
    last_round = max(e.round_number for s, e in races if s.status == "loaded")
    # Only rounds after the latest ingested one are treated as unrun; earlier un-ingested
    # rounds already happened but are missing from the data.
    remaining = sum(1 for _, e in races if e.round_number > last_round)
    missing = sorted(e.round_number for s, e in races if s.status != "loaded" and e.round_number < last_round)

    sprint_ids = list(db.scalars(
        select(m.SessionRow.id).join(m.Event).where(
            m.Event.season_id == season.id, m.SessionRow.session_type == "S", m.SessionRow.status == "loaded")
    ))
    entries = db.execute(
        select(m.SessionEntry, m.Driver.code, m.Constructor.name)
        .join(m.Driver).outerjoin(m.Constructor).where(m.SessionEntry.session_id.in_(done + sprint_ids))
    ).all()
    d_pts: dict[str, float] = {}
    t_pts: dict[str, float] = {}
    team_of: dict[str, str] = {}
    for e, code, team in entries:
        p = e.points or 0.0
        d_pts[code] = d_pts.get(code, 0.0) + p
        team = team or "Unknown"
        t_pts[team] = t_pts.get(team, 0.0) + p
        team_of[code] = team  # latest seen team

    n_done = len(done)
    ppr = {d: p / n_done for d, p in d_pts.items()}
    mean = sum(ppr.values()) / len(ppr)
    shrink = 0.8
    strengths = {d: (shrink * v + (1 - shrink) * mean + PRIOR_POINTS_PER_RACE) ** SHARPEN for d, v in ppr.items()}

    res = simulate_championship(
        year, sorted(d_pts), team_of, d_pts, t_pts, strengths, remaining, n_sims=n_sims, seed=seed,
    )
    return {
        "year": year, "races_completed": n_done, "races_remaining": remaining,
        "drivers": sorted(
            ({"driver": d, "points": d_pts[d], "win_probability": res.driver_win_prob[d]} for d in d_pts),
            key=lambda r: -r["win_probability"]),
        "constructors": sorted(
            ({"constructor": t, "points": t_pts.get(t, 0.0), "win_probability": p}
             for t, p in res.constructor_win_prob.items()),
            key=lambda r: -r["win_probability"]),
        "model_version": MODEL_VERSION, "n_simulations": res.n_sims, "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "missing_rounds": missing,
        "caveats": ["Probabilities are model estimates based on points-per-race form, not guarantees.",
                    "Remaining-race count is derived from the ingested schedule."]
                   + ([f"Rounds {missing} have not been ingested, so points and form are incomplete; "
                       "these probabilities are not meaningful until they are."] if missing else []),
    }
