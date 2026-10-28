"""Configurable race-outcome model (strengths + reliability) and its Monte Carlo simulator.

log strength_i = alpha * log(points-form strength_i) - beta * pace_rating_i - gamma * quali_rating_i

- points-form strength: the baseline from evaluation.form_strengths (season points per race, shrunk).
- pace_rating: recency-weighted race pace relative to the field (% ; negative = faster), shrunk toward the field
  and blended with the team's mean so a car's pace is shared between its two drivers.
- quali_rating: recency-weighted qualifying position minus the field's average (positions; negative = better).
alpha = 2.5, beta = gamma = 0 is exactly the baseline model. Every function reads only the history it is given;
callers pass rows of earlier rounds only.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.evaluation import DNF_PROB, form_strengths
from app.ml.features import canonical_team, weighted_mean_by_driver
from app.ml.simulation import finishing_ranks
from scipy.stats import spearmanr

PACE_PRIOR_RACES = 3.0     # pseudo-races pulling a rating toward the field mean
QUALI_PRIOR_RACES = 3.0
DNF_PRIOR_RACES = 10.0     # pseudo-starts pulling a retirement rate toward the pooled rate
DNF_BOUNDS = (0.01, 0.40)


@dataclass(frozen=True)
class ModelConfig:
    name: str
    alpha: float = 2.5        # exponent on the points-form strength
    beta: float = 0.0         # weight on pace rating (strength change per 1% of pace)
    gamma: float = 0.0        # weight on qualifying rating (strength change per grid place)
    pace_decay: float = 0.9   # recency weight base for pace and qualifying
    team_share: float = 0.5   # how much of a driver's pace rating comes from the team mean
    dnf_mode: str = "fixed"   # "fixed" or "shrunk"
    delta: float = 0.0        # weight on ln(grid position): strength is multiplied by position ** -delta
    kappa: float = 0.0        # exponent applied to the circuit factor that scales delta (0 = same everywhere)
    epsilon: float = 0.0      # weight on the team-at-this-circuit pace effect (strength change per 1% of pace)


BASELINE = ModelConfig("baseline")


def _shrunk(means: pd.Series, n_eff: pd.Series, prior: float, centre: float) -> pd.Series:
    return centre + n_eff / (n_eff + prior) * (means - centre)


def pace_ratings(history: pd.DataFrame, drivers: list[str], teams: dict[str, str], cfg: ModelConfig) -> dict[str, float]:
    """Pace rating per driver (% vs field; negative = faster). Unseen drivers get their team's, else 0."""
    mean, n_eff = weighted_mean_by_driver(history, "pace_pct", cfg.pace_decay)
    if mean.empty:
        return {d: 0.0 for d in drivers}
    centre = 0.0
    own = _shrunk(mean, n_eff, PACE_PRIOR_RACES, centre)
    team_of = history.sort_values("round").groupby("driver")["team"].last()
    team_mean = own.groupby(team_of.reindex(own.index)).mean()
    out = {}
    for d in drivers:
        t = teams.get(d) or team_of.get(d)
        team_r = team_mean.get(t, centre)
        if d in own.index:
            out[d] = cfg.team_share * team_r + (1 - cfg.team_share) * float(own[d])
        else:
            out[d] = float(team_r)
    return out


def quali_ratings(history: pd.DataFrame, drivers: list[str], cfg: ModelConfig) -> dict[str, float]:
    """Average qualifying position minus the field's, recency weighted and shrunk (negative = better)."""
    mean, n_eff = weighted_mean_by_driver(history, "quali_pos", cfg.pace_decay)
    if mean.empty:
        return {d: 0.0 for d in drivers}
    centre = float(mean.mean())
    own = _shrunk(mean, n_eff, QUALI_PRIOR_RACES, centre) - centre
    return {d: float(own.get(d, 0.0)) for d in drivers}


def log_strengths(history: pd.DataFrame, drivers: list[str], teams: dict[str, str], cfg: ModelConfig,
                  grid: dict[str, float] | None = None, circuit_factor: float = 1.0,
                  circuit_delta: dict[str, float] | None = None) -> np.ndarray:
    raw = form_strengths(history, decay=1.0)
    default = float(np.mean(list(raw.values()))) if raw else 1.0
    pts = np.array([raw.get(d, default) for d in drivers])
    out = cfg.alpha * np.log(pts)
    if cfg.beta:
        pr = pace_ratings(history, drivers, teams, cfg)
        out = out - cfg.beta * np.array([pr[d] for d in drivers])
    if cfg.gamma:
        qr = quali_ratings(history, drivers, cfg)
        out = out - cfg.gamma * np.array([qr[d] for d in drivers])
    if cfg.epsilon and circuit_delta:
        out = out - cfg.epsilon * np.array([circuit_delta.get(canonical_team(teams.get(d)), 0.0) for d in drivers])
    if cfg.delta and grid is not None:
        # a driver with no qualifying time is treated as starting at the back
        pos = np.array([grid.get(d) if grid.get(d) is not None and not np.isnan(grid.get(d)) else len(drivers) for d in drivers], float)
        out = out - cfg.delta * circuit_factor ** cfg.kappa * np.log(np.maximum(pos, 1.0))
    return out


def dnf_probabilities(dnf_history: pd.DataFrame, drivers: list[str], teams: dict[str, str], cfg: ModelConfig) -> np.ndarray:
    """Retirement probability per driver. "shrunk": average of the driver's and the team's own rate, each pulled
    toward the pooled rate, so a reliable car or a crash-prone driver shifts the estimate without small samples
    swinging it."""
    if cfg.dnf_mode == "fixed" or dnf_history.empty or "dnf" not in dnf_history.columns:
        return np.full(len(drivers), DNF_PROB)
    pooled = float(dnf_history["dnf"].mean())
    by_driver = dnf_history.groupby("driver")["dnf"].agg(["sum", "count"])
    by_team = dnf_history.groupby("team")["dnf"].agg(["sum", "count"])

    def rate(stats, key):
        if key not in stats.index:
            return pooled
        s, c = stats.loc[key, "sum"], stats.loc[key, "count"]
        return float((s + DNF_PRIOR_RACES * pooled) / (c + DNF_PRIOR_RACES))

    probs = np.array([0.5 * rate(by_driver, d) + 0.5 * rate(by_team, teams.get(d)) for d in drivers])
    return np.clip(probs, *DNF_BOUNDS)


def simulate_outcomes(log_s: np.ndarray, dnf: np.ndarray, n_sims: int = 20000, seed: int = 0) -> dict:
    """Sample finishing orders; returns per-driver position probabilities (finishers only), retirement
    probability and expected position (a retirement counts as last place)."""
    n = len(log_s)
    _, ranks, retired = finishing_ranks(np.random.default_rng(seed), log_s, dnf, n_sims)
    finished = ~retired
    pos_prob = np.stack([((ranks == k) & finished).mean(axis=0) for k in range(n)], axis=1)
    return {"pos_prob": pos_prob, "p_dnf": retired.mean(axis=0),
            "expected_position": np.where(retired, n, ranks + 1).mean(axis=0)}


def predict_race(history: pd.DataFrame, dnf_history: pd.DataFrame, lineup: dict[str, str], cfg: ModelConfig,
                 n_sims: int = 20000, seed: int = 0, grid: dict[str, float] | None = None,
                 circuit_factor: float = 1.0, circuit_delta: dict[str, float] | None = None) -> dict:
    """Forecast for `lineup` (driver -> team) given the rows of earlier races."""
    drivers = sorted(lineup)
    out = simulate_outcomes(log_strengths(history, drivers, lineup, cfg, grid, circuit_factor, circuit_delta),
                            dnf_probabilities(dnf_history, drivers, lineup, cfg), n_sims, seed)
    pp = out["pos_prob"]
    out.update(drivers=drivers, p_win=pp[:, 0], p_podium=pp[:, :3].sum(axis=1), p_top10=pp[:, :10].sum(axis=1))
    return out


# --- circuit overtaking difficulty -------------------------------------------------------------------------------
GRID_FACTOR_PRIOR_RACES = 3.0
GRID_FACTOR_BOUNDS = (0.5, 1.5)


def race_grid_correlations(rows: pd.DataFrame) -> pd.DataFrame:
    """Per past race: Spearman correlation between qualifying position and finishing position (how much the grid
    carried through to the flag). `rows`: year, round, circuit, quali_pos, finish."""
    out = []
    for (year, rnd, circuit), g in rows.dropna(subset=["quali_pos", "finish"]).groupby(["year", "round", "circuit"]):
        if len(g) >= 8 and g["quali_pos"].nunique() > 1:
            out.append({"year": year, "round": rnd, "circuit": circuit,
                        "rho": float(spearmanr(g["quali_pos"], g["finish"]).statistic)})
    return pd.DataFrame(out, columns=["year", "round", "circuit", "rho"])


def circuit_factor(prior_correlations: pd.DataFrame, circuit: str | None) -> float:
    """How strongly the grid decides the result at `circuit` relative to the average circuit (1 = average;
    above 1 = processional, below 1 = easy to overtake). Shrunk toward 1 with few past races, clipped."""
    if prior_correlations.empty or circuit is None:
        return 1.0
    pooled = float(prior_correlations["rho"].mean())
    here = prior_correlations[prior_correlations["circuit"] == circuit]["rho"]
    if pooled <= 0.05 or here.empty:
        return 1.0
    shrunk = (len(here) * float(here.mean()) + GRID_FACTOR_PRIOR_RACES * pooled) / (len(here) + GRID_FACTOR_PRIOR_RACES)
    return float(np.clip(shrunk / pooled, *GRID_FACTOR_BOUNDS))
