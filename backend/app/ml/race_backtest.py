"""Rolling full-order backtest of race models.

Every prediction for race r uses only races before r (this season's earlier rounds; retirement rates may also use
earlier seasons). Models are scored on the whole classification, not just the winner:
  - log loss for win / podium / top-10 / retirement probabilities,
  - Spearman rank correlation between predicted and actual finishing order,
  - mean absolute error of expected vs actual finishing position.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from app.ml.features import team_circuit_deltas
from app.ml.race_model import ModelConfig, circuit_factor, predict_race, race_grid_correlations

EPS = 1e-6
BASELINE_RANKERS = ("last race result", "championship order")
GRID_RANKER = "grid order"   # post-qualifying baseline: finish where you qualified
MIN_GRID_SHARE = 0.8          # a race needs qualifying positions for this share of drivers to be a post-qualifying race


def _rank_baseline(kind: str, history: pd.DataFrame, drivers: list[str], grid: dict | None = None) -> np.ndarray:
    """Expected-position stand-ins that need no probabilities: previous race's result, points standing, or the grid."""
    n = len(drivers)
    if kind == GRID_RANKER:
        vals = np.array([(grid or {}).get(d, np.nan) for d in drivers], dtype=float)
    elif kind == "last race result":
        last = history[history["round"] == history["round"].max()].set_index("driver")["finish"]
        vals = np.array([last.get(d, np.nan) for d in drivers], dtype=float)
    else:
        pts = (history["race_points"] + history["sprint_points"]).groupby(history["driver"]).sum()
        order = pts.rank(ascending=False, method="min")
        vals = np.array([order.get(d, np.nan) for d in drivers], dtype=float)
    return np.where(np.isnan(vals), np.nanmean(vals) if np.isfinite(vals).any() else (n + 1) / 2, vals)


def collect(hist_by_year: dict[int, pd.DataFrame], configs: list[ModelConfig], min_train_rounds: int = 4,
            n_sims: int = 4000, seed: int = 0, years: list[int] | None = None, rankers=BASELINE_RANKERS,
            need_grid: bool = False) -> pd.DataFrame:
    """Long frame: one row per (config, year, round, driver) with the prediction and the actual outcome.

    Qualifying positions of the race being predicted are available to the model (they are known before the race);
    its finishing results are not. With `need_grid`, races without qualifying data are skipped."""
    rows = []
    sorted_years = sorted(hist_by_year)
    corr_all = None
    if any(c.kappa for c in configs):
        stacked = pd.concat([h.assign(year=y) for y, h in hist_by_year.items()], ignore_index=True)
        corr_all = race_grid_correlations(stacked)
    for year in (years or sorted_years):
        season = hist_by_year[year]
        earlier = [hist_by_year[y] for y in sorted_years if y < year]
        for rnd in sorted(r for r in season["round"].unique() if r > min_train_rounds):
            history = season[season["round"] < rnd]
            actual = season[season["round"] == rnd].drop_duplicates("driver").set_index("driver")
            dnf_history = pd.concat([*earlier, history], ignore_index=True)
            lineup = dict(zip(actual.index, actual["team"]))
            drivers = sorted(lineup)
            grid = actual["quali_pos"].to_dict() if "quali_pos" in actual else {}
            has_grid = len(drivers) > 0 and np.mean([not np.isnan(grid.get(d, np.nan)) for d in drivers]) >= MIN_GRID_SHARE
            if need_grid and not has_grid:
                continue
            cdelta = None
            if any(c.epsilon for c in configs):
                cdelta = team_circuit_deltas([hist_by_year[y] for y in sorted_years if y < year],
                                             actual["circuit"].iloc[0] if "circuit" in actual else None)
            cf = 1.0
            if corr_all is not None:
                before = corr_all[(corr_all["year"] < year) | ((corr_all["year"] == year) & (corr_all["round"] < rnd))]
                cf = circuit_factor(before, actual["circuit"].iloc[0] if "circuit" in actual else None)
            base = {"year": year, "round": rnd}
            actual_cols = {"finish": actual.loc[drivers, "finish"].to_numpy(), "dnf": actual.loc[drivers, "dnf"].to_numpy()}
            for cfg in configs:
                pred = predict_race(history, dnf_history, lineup, cfg, n_sims, seed, grid=grid if has_grid else None,
                                    circuit_factor=cf, circuit_delta=cdelta)
                rows.append(pd.DataFrame({
                    **base, "config": cfg.name, "driver": drivers, "exp_pos": pred["expected_position"],
                    "p_win": pred["p_win"], "p_podium": pred["p_podium"], "p_top10": pred["p_top10"],
                    "p_dnf": pred["p_dnf"], **actual_cols}))
            n = len(drivers)
            uniform = pd.DataFrame({**base, "config": "uniform", "driver": drivers, "exp_pos": (n + 1) / 2,
                                    "p_win": 1 / n, "p_podium": min(3 / n, 1), "p_top10": min(10 / n, 1),
                                    "p_dnf": float(dnf_history["dnf"].mean()), **actual_cols})
            rows.append(uniform)
            for kind in rankers:
                rows.append(pd.DataFrame({**base, "config": kind, "driver": drivers,
                                          "exp_pos": _rank_baseline(kind, history, drivers, grid), "p_win": np.nan,
                                          "p_podium": np.nan, "p_top10": np.nan, "p_dnf": np.nan, **actual_cols}))
    return pd.concat(rows, ignore_index=True)


def _ll(y, p) -> float:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def race_scores(pred: pd.DataFrame) -> pd.DataFrame:
    """One row per (config, year, round): the metrics for that race."""
    out = []
    for (cfg, year, rnd), g in pred.groupby(["config", "year", "round"]):
        finish = g["finish"].to_numpy(float)
        rho = spearmanr(g["exp_pos"], finish).statistic if g["exp_pos"].nunique() > 1 else 0.0
        row = {"config": cfg, "year": year, "round": rnd, "spearman": float(rho),
               "mae": float(np.mean(np.abs(g["exp_pos"].to_numpy(float) - finish)))}
        if g["p_win"].notna().all():
            row.update(ll_win=_ll(finish == 1, g["p_win"]), ll_podium=_ll(finish <= 3, g["p_podium"]),
                       ll_top10=_ll(finish <= 10, g["p_top10"]), ll_dnf=_ll(g["dnf"], g["p_dnf"]))
        out.append(row)
    return pd.DataFrame(out)


def pooled_probability_loss(scores: pd.DataFrame, config: str, years: list[int] | None = None) -> float:
    """Mean of the win / podium / top-10 log losses over the config's races (lower is better)."""
    s = scores[scores["config"] == config]
    if years is not None:
        s = s[s["year"].isin(years)]
    return float(s[["ll_win", "ll_podium", "ll_top10"]].mean().mean())


def paired_difference(scores: pd.DataFrame, a: str, b: str, metric: str, years: list[int] | None = None,
                      n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean of (metric_a - metric_b) over the same races, with a 95% bootstrap interval over races."""
    sa, sb = (scores[scores["config"] == c].set_index(["year", "round"])[metric] for c in (a, b))
    d = (sa - sb).dropna()
    if years is not None:
        d = d[d.index.get_level_values("year").isin(years)]
    rng = np.random.default_rng(seed)
    vals = d.to_numpy()
    boots = [rng.choice(vals, len(vals)).mean() for _ in range(n_boot)]
    return {"mean": float(vals.mean()), "low": float(np.percentile(boots, 2.5)), "high": float(np.percentile(boots, 97.5)),
            "n_races": int(len(vals))}
