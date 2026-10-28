"""Per-race feature table used by the race models and their backtest.

One row per (round, driver) for the races of one season, with everything a forecast made *before* that race
may use about earlier races: finishing position, points, retirement flag, race pace relative to the field,
and qualifying position. The model code is responsible for only reading rows of earlier rounds.
"""

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.analytics import season_metrics as sm
from app.services import frames

HISTORY_COLUMNS = ["round", "driver", "team", "circuit", "finish", "grid", "status", "race_points", "sprint_points",
                   "quali_pos", "pace_pct", "dnf"]


def season_history(db: Session, year: int) -> pd.DataFrame:
    """Race rows for `year` (loaded races only). `pace_pct` is the driver's median clean-lap pace relative to
    the field's that race (negative = faster; NaN when too few clean laps). `quali_pos` is the qualifying position."""
    ent = frames.entries_frame(db, year, types=("R", "Q", "S"))
    if ent.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    race = ent[ent["stype"] == "R"][["round", "driver", "team", "circuit", "finish", "grid", "status", "points"]].rename(
        columns={"points": "race_points"})
    sprint = ent[ent["stype"] == "S"][["round", "driver", "points"]].rename(columns={"points": "sprint_points"})
    quali = ent[ent["stype"] == "Q"][["round", "driver", "finish"]].rename(columns={"finish": "quali_pos"})
    pace = sm.race_pace_table(frames.season_laps_frame(db, year, "R"))[["round", "driver", "pace_delta_pct"]].rename(
        columns={"pace_delta_pct": "pace_pct"})

    df = (race.merge(sprint, on=["round", "driver"], how="left").merge(quali, on=["round", "driver"], how="left")
          .merge(pace, on=["round", "driver"], how="left"))
    df["sprint_points"] = df["sprint_points"].fillna(0.0)
    df["race_points"] = df["race_points"].fillna(0.0)
    df["dnf"] = df["status"].map(sm.is_dnf).astype(bool)
    df["team"] = df["team"].fillna("Unknown")
    return df[HISTORY_COLUMNS].sort_values(["round", "finish"]).reset_index(drop=True)


def all_histories(db: Session, years: list[int]) -> dict[int, pd.DataFrame]:
    return {y: season_history(db, y) for y in years}


def weighted_mean_by_driver(history: pd.DataFrame, column: str, decay: float) -> tuple[pd.Series, pd.Series]:
    """Exponentially recency-weighted mean of `column` per driver (weights decay**(last_round - round)), and the
    total weight ('effective number of races') behind each mean. NaN values are ignored."""
    h = history.dropna(subset=[column])
    if h.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    last = history["round"].max()
    w = decay ** (last - h["round"].to_numpy())
    g = h.assign(_w=w, _wx=w * h[column].to_numpy()).groupby("driver")
    n_eff = g["_w"].sum()
    return g["_wx"].sum() / n_eff, n_eff


def field_pace_check(history: pd.DataFrame) -> float:
    """Mean pace_pct over the history; close to 0 by construction (pace is relative to the field median)."""
    v = history["pace_pct"].dropna()
    return float(np.mean(v)) if len(v) else 0.0


def dnf_history(db: Session) -> pd.DataFrame:
    """Every loaded race of every season: (driver, team, dnf). Cheap (no lap data), used for retirement rates."""
    ent = frames.entries_frame(db, None, types=("R",))
    if ent.empty:
        return pd.DataFrame(columns=["driver", "team", "dnf"])
    out = ent[["driver", "team", "status"]].copy()
    out["team"] = out["team"].fillna("Unknown")
    out["dnf"] = out["status"].map(sm.is_dnf).astype(bool)
    return out[["driver", "team", "dnf"]]


# The same team under different names in different seasons (a rename or a new owner of the same entry).
TEAM_ALIASES = {"RB": "Racing Bulls", "AlphaTauri": "Racing Bulls", "Kick Sauber": "Audi", "Alfa Romeo": "Audi"}
CIRCUIT_PRIOR_VISITS = 2.0   # pseudo-visits pulling a team's circuit effect toward zero


def canonical_team(name: str | None) -> str:
    return TEAM_ALIASES.get(str(name), str(name))


def team_circuit_deltas(prior: list[pd.DataFrame], circuit: str | None, prior_visits: float = CIRCUIT_PRIOR_VISITS) -> dict[str, float]:
    """How much faster (negative) or slower (positive) each team was at `circuit` than its own average that season,
    in % of race pace, averaged over past visits and shrunk toward 0 (few visits, and cars change every year).

    `prior` are season histories of EARLIER seasons only (each with team, circuit, round, pace_pct). The field-wide
    mean of a visit is removed so the effect is relative to the other teams that weekend."""
    if circuit is None:
        return {}
    per_team: dict[str, list[float]] = {}
    for df in prior:
        if df.empty or "circuit" not in df or "pace_pct" not in df:
            continue
        d = df.dropna(subset=["pace_pct"]).assign(team=lambda x: x["team"].map(canonical_team))
        season_mean = d.groupby("team")["pace_pct"].mean()
        here = d[d["circuit"] == circuit]
        for _, visit in here.groupby("round"):
            at = visit.groupby("team")["pace_pct"].mean()
            delta = (at - season_mean.reindex(at.index)).dropna()
            if len(delta) < 3:
                continue
            delta = delta - delta.mean()
            for team, v in delta.items():
                per_team.setdefault(team, []).append(float(v))
    return {t: sum(v) / (len(v) + prior_visits) for t, v in per_team.items()}
