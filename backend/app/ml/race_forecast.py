"""Full-race forecast for an upcoming Grand Prix.

Two modes, upgraded automatically when qualifying results are available:

- pre-qualifying: strength = points-per-race form this season (shrunk, sharpened); grid unknown and unused.
- post-qualifying: the same form strength (exponent 1.5) times grid_position ** -2.0, with the qualifying order used
  as the starting grid.

Finishing orders are sampled from a Plackett-Luce model with retirement chances estimated per driver and team,
giving a probability for every finishing position plus win / podium / points / retirement probabilities and expected
points. Weather, safety cars and first-lap incidents are not modelled. Only results of earlier rounds are used.

Evidence for each choice is in docs/evaluation-race-model.md (retirement rates adopted; richer strength model not
adopted), docs/evaluation-grid-model.md (grid model adopted; per-circuit grid weight not adopted) and
docs/evaluation-circuit-effect.md (team-by-circuit pace effect tested; not adopted).
"""

from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.ml.evaluation import form_strengths
from app.ml.race_model import BASELINE, ModelConfig, predict_race
from app.ml.simulation import race_points_table

MODEL_VERSION_PRE = "race-form-baseline-dnf-shrunk-v2"
MODEL_VERSION_POST = "race-grid-a1.5-d2.0-dnf-shrunk-v3"
MODEL_VERSION = MODEL_VERSION_PRE                       # kept for older imports
MODE_PRE_QUALIFYING = "pre-qualifying"
MODE_POST_QUALIFYING = "post-qualifying"
MIN_GRID_SHARE = 0.8                                     # share of the lineup that must have qualified

PRE_CONFIG = replace(BASELINE, name="baseline-dnf-shrunk", dnf_mode="shrunk")
GRID_CONFIG = ModelConfig("grid-a1.5-d2.0-dnf-shrunk", alpha=1.5, delta=2.0, kappa=0.0, dnf_mode="shrunk")
FORECAST_CONFIG = PRE_CONFIG                              # kept for older imports

# quali: driver code -> (qualifying position, team name or None)
Qualifying = dict[str, tuple[float, str | None]]


class ForecastError(Exception):
    """The forecast cannot be produced (e.g. no results yet); the message is safe to show to users."""


def _lineup_from_history(history: pd.DataFrame) -> tuple[dict[str, str], int, list[dict]]:
    """Latest race's drivers and teams, the round they came from, and notes about drivers left out."""
    last_round = int(history["round"].max())
    last = history[history["round"] == last_round]
    lineup = dict(zip(last["driver"], last["team"].fillna("Unknown")))
    notes = []
    for driver, grp in history[~history["driver"].isin(lineup)].groupby("driver"):
        notes.append({"driver": driver, "team": grp.sort_values("round")["team"].iloc[-1],
                      "races": int(grp["round"].nunique()),
                      "note": f"{driver} raced {grp['round'].nunique()} round(s) this season but was not in the latest race, "
                              "so is not in this forecast."})
    return lineup, last_round, notes


def forecast_race(history: pd.DataFrame, year: int, names: dict[str, str] | None = None,
                  n_sims: int = 20000, seed: int = 0, dnf_history: pd.DataFrame | None = None,
                  quali: Qualifying | None = None) -> dict:
    """`history`: rows (round, driver, team, finish, race_points, sprint_points) of races ALREADY run this season.
    `dnf_history`: (driver, team, dnf) rows of all earlier races, any season (defaults to `history` if it has them).
    `quali`: qualifying results of THIS race; when it covers enough of the field, the grid model is used."""
    if history.empty:
        raise ForecastError("No completed races this season yet, so there is nothing to base a forecast on.")
    lineup, lineup_round, notes = _lineup_from_history(history)

    grid = None
    if quali and len(quali) >= MIN_GRID_SHARE * len(lineup):
        # The cars that actually qualified are the entrants; their qualifying order is the grid.
        entrants = {d: (t or lineup.get(d) or "Unknown") for d, (_, t) in quali.items()}
        for d in sorted(set(lineup) - set(entrants)):
            notes.append({"driver": d, "team": lineup[d], "races": None,
                          "note": f"{d} was in the latest race but has no qualifying result, so is not in this forecast."})
        lineup, grid = entrants, {d: float(pos) for d, (pos, _) in quali.items()}
    mode = MODE_POST_QUALIFYING if grid is not None else MODE_PRE_QUALIFYING
    cfg = GRID_CONFIG if grid is not None else PRE_CONFIG

    drivers = sorted(lineup)
    n = len(drivers)
    raw = form_strengths(history, decay=1.0)
    out = predict_race(history, history if dnf_history is None else dnf_history, lineup, cfg, n_sims, seed, grid=grid)
    pos_prob, p_dnf, expected_pos = out["pos_prob"], out["p_dnf"], out["expected_position"]

    points = np.array(race_points_table(year) + [0] * max(0, n - 10), dtype=float)[:n]
    exp_points = pos_prob @ points

    rows = []
    for i, d in enumerate(drivers):
        rows.append({
            "driver": d, "name": (names or {}).get(d), "team": lineup[d],
            "grid": None if grid is None else int(grid[d]),
            "expected_position": round(float(expected_pos[i]), 2),
            "expected_points": round(float(exp_points[i]), 2),
            "p_win": round(float(pos_prob[i, 0]), 4),
            "p_podium": round(float(pos_prob[i, :3].sum()), 4),
            "p_points": round(float(pos_prob[i, :10].sum()), 4),
            "p_dnf": round(float(p_dnf[i]), 4),
            "position_probs": [round(float(x), 4) for x in pos_prob[i]],
            "has_history": d in raw,
        })
    rows.sort(key=lambda r: (r["expected_position"], r["driver"]))
    for pos, r in enumerate(rows, 1):
        r["predicted_rank"] = pos

    teams: dict[str, float] = {}
    for r in rows:
        teams[r["team"]] = teams.get(r["team"], 0.0) + r["expected_points"]
    constructors = sorted(({"team": t, "expected_points": round(v, 2)} for t, v in teams.items()),
                          key=lambda x: -x["expected_points"])

    if grid is None:
        caveats = [
            "Pre-qualifying forecast: grid positions are not known yet and are not used. It upgrades automatically "
            "once this weekend's qualifying has been ingested.",
            "Baseline model: this season's points-per-race form only (it does not see car pace). Weather, safety cars, "
            "strategy and first-lap incidents are not modelled.",
            "Why every upcoming race looks the same before qualifying: they are all forecast from the same results, and a "
            "team-by-circuit effect from past seasons was tested and did not predict better (docs/evaluation-circuit-effect.md), "
            "so the model does not distinguish circuits. Races separate once qualifying is in, because the grid differs.",
        ]
    else:
        caveats = [
            "Post-qualifying forecast: the qualifying order is used as the starting grid. Grid penalties and pit-lane "
            "starts are not known at this point and are not reflected.",
            "Model: this season's points-per-race form plus the starting grid (backtested over 54 races: clearly better "
            "calibrated than the pre-qualifying model, but its ordering is about the same as the qualifying order). "
            "Weather, safety cars, strategy and first-lap incidents are not modelled.",
        ]
    caveats += [
        "Retirement chances are estimated per driver and team from earlier races (shrunk toward the average), "
        f"typically {float(np.median(p_dnf)):.0%} per driver.",
        "Probabilities, not predictions of a single result: the table is ordered by expected finishing position "
        "(a retirement counts as last), not by the single most likely order.",
    ]
    if any(not r["has_history"] for r in rows):
        caveats.append("Drivers without a result this season are given the field-average strength.")

    return {
        "model_version": MODEL_VERSION_POST if grid is not None else MODEL_VERSION_PRE, "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_round": int(history["round"].max()), "lineup_from_round": lineup_round,
        "n_simulations": n_sims, "seed": seed,
        "drivers": rows, "constructors": constructors, "lineup_notes": notes, "caveats": caveats,
        "positions": n,
    }
