"""Scoring forecasts against what actually happened (pure functions).

A forecast is the dict produced by race_forecast.forecast_race. `actual` maps driver code -> classified finishing
position (retirements are classified behind the finishers, as in the results data).
"""

import numpy as np
from scipy.stats import spearmanr

MIN_DRIVERS = 8
CAL_BINS = (0.0, 0.02, 0.05, 0.10, 0.20, 0.40, 0.70, 1.0001)
TARGETS = {"win": ("p_win", 1), "podium": ("p_podium", 3), "points": ("p_points", 10)}


def score_forecast(drivers: list[dict], actual: dict[str, int]) -> tuple[dict, dict[str, list[tuple[float, int]]]] | None:
    """Metrics for one race and the (probability, outcome) pairs used for calibration.

    Only drivers present in both the forecast and the results are scored; returns None when fewer than MIN_DRIVERS
    overlap (a forecast for the wrong field is not scored rather than scored badly)."""
    common = [d for d in drivers if d["driver"] in actual]
    if len(common) < MIN_DRIVERS:
        return None
    exp = np.array([d["expected_position"] for d in common], float)
    fin = np.array([actual[d["driver"]] for d in common], float)
    rho = float(spearmanr(exp, fin).statistic) if len(set(exp)) > 1 else 0.0

    by_rank = sorted(common, key=lambda d: d["predicted_rank"])
    predicted_top3 = [d["driver"] for d in by_rank[:3]]
    actual_top3 = [d for d, _ in sorted(actual.items(), key=lambda kv: kv[1])[:3]]
    winner = actual_top3[0]
    winner_row = next((d for d in common if d["driver"] == winner), None)

    score = {
        "drivers_scored": len(common), "drivers_missing": len(actual) - len(common),
        "spearman": rho, "mean_position_error": float(np.mean(np.abs(exp - fin))),
        "winner": winner, "winner_p_win": None if winner_row is None else winner_row["p_win"],
        "winner_predicted_rank": None if winner_row is None else winner_row["predicted_rank"],
        "predicted_top3": predicted_top3, "actual_top3": actual_top3,
        "podium_overlap": len(set(predicted_top3) & set(actual_top3)),
        "chance_win_p": 1.0 / len(common),
    }
    pairs = {t: [(float(d[key]), int(actual[d["driver"]] <= k)) for d in common] for t, (key, k) in TARGETS.items()}
    return score, pairs


def summarise(scores: list[dict]) -> dict:
    """Aggregate per-race scores. Winner statistics only count races whose winner was in the forecast field."""
    if not scores:
        return {"races": 0}
    with_winner = [s for s in scores if s["winner_p_win"] is not None]
    return {
        "races": len(scores),
        "mean_spearman": float(np.mean([s["spearman"] for s in scores])),
        "mean_position_error": float(np.mean([s["mean_position_error"] for s in scores])),
        "winner_in_predicted_top3": int(sum(1 for s in with_winner if s["winner_predicted_rank"] <= 3)),
        "winner_predicted_first": int(sum(1 for s in with_winner if s["winner_predicted_rank"] == 1)),
        "winners_scored": len(with_winner),
        "mean_p_win_given_to_winner": float(np.mean([s["winner_p_win"] for s in with_winner])) if with_winner else None,
        "mean_chance_level_p_win": float(np.mean([s["chance_win_p"] for s in scores])),
        "mean_podium_overlap": float(np.mean([s["podium_overlap"] for s in scores])),
    }


def calibration_table(pairs: list[tuple[float, int]], bins=CAL_BINS) -> list[dict]:
    """Reliability table: for each probability bin, the mean forecast and the observed frequency. Empty bins are
    omitted. Few races means few cases per bin, so `n` is reported and small bins should not be over-read."""
    if not pairs:
        return []
    p = np.array([x[0] for x in pairs], float)
    y = np.array([x[1] for x in pairs], float)
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (p >= lo) & (p < hi)
        if m.any():
            out.append({"low": lo, "high": min(hi, 1.0), "n": int(m.sum()), "mean_predicted": float(p[m].mean()),
                        "observed_rate": float(y[m].mean())})
    return out
