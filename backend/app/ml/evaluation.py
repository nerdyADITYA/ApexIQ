"""Chronological backtesting.

`results` is a DataFrame with one row per (round, driver):
  round, driver, team, finish (1-based), race_points, sprint_points.
Every prediction for round r is built from rows with round < r only.
"""

import numpy as np
import pandas as pd

from app.ml.simulation import finishing_ranks, simulate_championship

PRIOR = 2.0
SHRINK = 0.8
DNF_PROB = 0.05
EPS = 1e-6
TARGETS = {"win": 1, "podium": 3, "top10": 10}


def form_strengths(history: pd.DataFrame, decay: float) -> dict[str, float]:
    """Exponentially weighted points-per-race, shrunk toward the field mean.
    decay=1.0 is the plain season average. Uses ONLY the rows passed in."""
    if history.empty:
        return {}
    last = history["round"].max()
    w = decay ** (last - history["round"])
    h = history.assign(w=w, wp=w * history["race_points"])
    g = h.groupby("driver")
    ppr = g["wp"].sum() / g["w"].sum()
    mean = ppr.mean()
    return (SHRINK * ppr + (1 - SHRINK) * mean + PRIOR).to_dict()


def race_probabilities(strengths: dict[str, float], drivers: list[str], n_sims=4000, seed=0,
                       sharpen: float = 1.0) -> pd.DataFrame:
    """P(win / podium / top10) per driver. Unseen drivers get the field-average strength.
    Plackett-Luce weight is strength**sharpen: sharpen > 1 spreads probabilities apart."""
    default = float(np.mean(list(strengths.values()))) if strengths else 1.0
    logs = sharpen * np.log(np.array([max(strengths.get(d, default), EPS) for d in drivers]))
    _, ranks, retired = finishing_ranks(np.random.default_rng(seed), logs, np.full(len(drivers), DNF_PROB), n_sims)
    out = {name: ((ranks < k) & ~retired).mean(axis=0) for name, k in TARGETS.items()}
    return pd.DataFrame(out, index=drivers)


def uniform_probabilities(drivers: list[str]) -> pd.DataFrame:
    n = len(drivers)
    return pd.DataFrame({name: min(k / n, 1.0) for name, k in TARGETS.items()}, index=drivers)


def log_loss(y, p) -> float:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def calibration_table(y, p, bins=(0, 0.02, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0001)) -> pd.DataFrame:
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.cut(df["p"], bins, right=False)
    t = df.groupby("bin", observed=True).agg(n=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean"))
    return t.reset_index()


MODELS = {
    "uniform": None,
    "season-form (decay 1.0)": 1.0,
    "recent-form (decay 0.8)": 0.8,
}


def backtest_races(results: pd.DataFrame, min_train_rounds: int = 4, n_sims=4000, seed=0) -> pd.DataFrame:
    """Long frame of predictions: one row per (model, round, driver, target)."""
    rows = []
    for rnd in sorted(r for r in results["round"].unique() if r > min_train_rounds):
        history = results[results["round"] < rnd]           # strict: nothing from round >= rnd
        actual = results[results["round"] == rnd].set_index("driver")
        drivers = list(actual.index)
        for model, decay in MODELS.items():
            probs = (uniform_probabilities(drivers) if decay is None
                     else race_probabilities(form_strengths(history, decay), drivers, n_sims, seed))
            for target, k in TARGETS.items():
                y = (actual["finish"] <= k).astype(int)
                rows.append(pd.DataFrame({"model": model, "round": rnd, "driver": drivers, "target": target,
                                          "p": probs[target].to_numpy(), "y": y.to_numpy()}))
    return pd.concat(rows, ignore_index=True)


ALPHAS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)
NESTED = "recent-form + nested sharpening"


def _pooled_loss(rows: pd.DataFrame) -> float:
    return log_loss(rows["y"], rows["p"])


def predictions_by_alpha(results: pd.DataFrame, decay=0.8, alphas=ALPHAS, min_train_rounds=4,
                         n_sims=4000, seed=0) -> dict[float, pd.DataFrame]:
    """For every alpha, the long prediction frame (round, driver, target, p, y) for rounds
    > min_train_rounds. Each round's strengths use only earlier rounds."""
    rounds = sorted(r for r in results["round"].unique() if r > min_train_rounds)
    by_alpha: dict[float, list[pd.DataFrame]] = {a: [] for a in alphas}
    for rnd in rounds:
        history = results[results["round"] < rnd]
        actual = results[results["round"] == rnd].set_index("driver")
        drivers = list(actual.index)
        strengths = form_strengths(history, decay)
        for a in alphas:
            probs = race_probabilities(strengths, drivers, n_sims, seed, sharpen=a)
            by_alpha[a].append(pd.concat([
                pd.DataFrame({"round": rnd, "driver": drivers, "target": t, "p": probs[t].to_numpy(),
                              "y": (actual["finish"] <= k).astype(int).to_numpy()})
                for t, k in TARGETS.items()]))
    return {a: pd.concat(v, ignore_index=True) for a, v in by_alpha.items()}


def best_alpha(frames: dict[float, pd.DataFrame], rounds=None) -> float:
    """Alpha with the lowest pooled log loss over `rounds` (all rounds if None)."""
    losses = {a: _pooled_loss(df if rounds is None else df[df["round"].isin(rounds)]) for a, df in frames.items()}
    return min(losses, key=losses.get)


def backtest_sharpened(results: pd.DataFrame, decay=0.8, alphas=ALPHAS, min_train_rounds=4,
                       n_sims=4000, seed=0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expanding-window selection of the sharpening exponent.

    For round r, alpha is the grid value with the lowest pooled log loss over the
    already-completed prediction rounds (min_train_rounds < k < r), whose outcomes
    are known by round r. The first predicted round has no such history and uses
    alpha = 1.0. Returns (predictions for the nested model, chosen alpha per round)."""
    frames = predictions_by_alpha(results, decay, alphas, min_train_rounds, n_sims, seed)
    rounds = sorted(next(iter(frames.values()))["round"].unique())
    chosen, parts = [], []
    for rnd in rounds:
        past = [r for r in rounds if r < rnd]
        alpha = best_alpha(frames, past) if past else 1.0
        chosen.append({"round": rnd, "alpha": alpha})
        parts.append(frames[alpha][frames[alpha]["round"] == rnd].assign(model=NESTED))
    return pd.concat(parts, ignore_index=True), pd.DataFrame(chosen)


def summarise(pred: pd.DataFrame, n_boot=2000, seed=0) -> pd.DataFrame:
    """Per model/target metrics plus a bootstrap-over-races 95% CI of the log-loss gain vs uniform."""
    rng = np.random.default_rng(seed)
    rows = []
    rounds = np.sort(pred["round"].unique())
    for target, g in pred.groupby("target"):
        per_round = {m: gg.groupby("round").apply(lambda d: log_loss(d["y"], d["p"]), include_groups=False)
                     for m, gg in g.groupby("model")}
        for model, gg in g.groupby("model"):
            gain = per_round["uniform"] - per_round[model]
            boots = [gain.loc[rng.choice(rounds, len(rounds))].mean() for _ in range(n_boot)]
            rows.append({"target": target, "model": model, "n": len(gg),
                         "log_loss": log_loss(gg["y"], gg["p"]), "brier": brier(gg["y"], gg["p"]),
                         "gain_vs_uniform": float(gain.mean()),
                         "gain_ci_low": float(np.percentile(boots, 2.5)), "gain_ci_high": float(np.percentile(boots, 97.5))})
    return pd.DataFrame(rows)


def backtest_championship(results: pd.DataFrame, champion: str | None, total_rounds: int, decay=1.0,
                          min_train_rounds=3, n_sims=4000, seed=0, year=2024, sharpen=1.0) -> pd.DataFrame:
    """After each round r, P(actual champion). One season = one outcome: illustrative, not statistical evidence.

    `year` selects the scoring rules (the fastest-lap point existed only 2019-2024). `sharpen` is the
    strength exponent. `champion` may be None for an unfinished season (then only the leader is reported).
    Rounds run up to the last round present in `results`, so partial seasons work."""
    rows = []
    last_loaded = int(results["round"].max())
    for r in range(min_train_rounds, min(total_rounds, last_loaded + 1)):
        hist = results[results["round"] <= r]
        pts = (hist["race_points"] + hist["sprint_points"]).groupby(hist["driver"]).sum()
        team_pts = (hist["race_points"] + hist["sprint_points"]).groupby(hist["team"]).sum()
        team_of = hist.sort_values("round").groupby("driver")["team"].last().to_dict()
        s = {d: v ** sharpen for d, v in form_strengths(hist, decay).items()}
        res = simulate_championship(year, sorted(pts.index), team_of, pts.to_dict(), team_pts.to_dict(), s,
                                    total_rounds - r, n_sims=n_sims, seed=seed)
        rows.append({"after_round": r,
                     "p_actual_champion": None if champion is None else res.driver_win_prob.get(champion, 0.0),
                     "leader": pts.idxmax(), "leader_p": res.driver_win_prob[pts.idxmax()]})
    return pd.DataFrame(rows)
