import numpy as np
import pytest

from app.ml.track_record import calibration_table, score_forecast, summarise


def forecast(n=10, order=None, p_win=None):
    """A forecast whose predicted order is `order` (default D0..Dn-1)."""
    order = order or [f"D{i}" for i in range(n)]
    drivers = []
    for rank, d in enumerate(order, 1):
        drivers.append({"driver": d, "predicted_rank": rank, "expected_position": float(rank),
                        "p_win": (p_win or {}).get(d, 0.5 if rank == 1 else 0.05),
                        "p_podium": 0.7 if rank <= 3 else 0.1, "p_points": 0.9 if rank <= 10 else 0.2})
    return drivers


def test_perfect_forecast_scores_perfectly():
    d = forecast()
    actual = {x["driver"]: x["predicted_rank"] for x in d}
    score, pairs = score_forecast(d, actual)
    assert score["spearman"] == pytest.approx(1.0) and score["mean_position_error"] == 0.0
    assert score["winner"] == "D0" and score["winner_predicted_rank"] == 1 and score["podium_overlap"] == 3
    assert score["drivers_missing"] == 0 and score["chance_win_p"] == pytest.approx(0.1)
    assert [y for _, y in pairs["win"]].count(1) == 1 and [y for _, y in pairs["podium"]].count(1) == 3
    assert len(pairs["points"]) == 10


def test_reversed_result_scores_minus_one_and_misses_the_podium():
    d = forecast()
    actual = {x["driver"]: 11 - x["predicted_rank"] for x in d}
    score, _ = score_forecast(d, actual)
    assert score["spearman"] == pytest.approx(-1.0) and score["podium_overlap"] == 0
    assert score["winner"] == "D9" and score["winner_predicted_rank"] == 10


def test_only_common_drivers_are_scored_and_a_wrong_field_is_not_scored_at_all():
    d = forecast(12)
    actual = {x["driver"]: x["predicted_rank"] for x in d[:9]}
    actual["NEW"] = 10                                         # a driver the forecast did not have
    score, pairs = score_forecast(d, actual)
    assert score["drivers_scored"] == 9 and score["drivers_missing"] == 1 and len(pairs["win"]) == 9
    assert score_forecast(d, {"D0": 1, "D1": 2, "X": 3}) is None


def test_winner_outside_the_forecast_field_is_handled():
    d = forecast(10)
    actual = {x["driver"]: x["predicted_rank"] + 1 for x in d}   # everyone shifts back one place
    actual["OUTSIDER"] = 1                                       # and someone not in the forecast wins
    score, _ = score_forecast(d, actual)
    assert score["winner"] == "OUTSIDER" and score["winner_p_win"] is None and score["winner_predicted_rank"] is None
    s = summarise([score])
    assert s["races"] == 1 and s["winners_scored"] == 0 and s["mean_p_win_given_to_winner"] is None


def test_summary_aggregates_races():
    d = forecast()
    good, _ = score_forecast(d, {x["driver"]: x["predicted_rank"] for x in d})
    bad, _ = score_forecast(d, {x["driver"]: 11 - x["predicted_rank"] for x in d})
    s = summarise([good, bad])
    assert s["races"] == 2 and s["mean_spearman"] == pytest.approx(0.0)
    assert s["winner_in_predicted_top3"] == 1 and s["winner_predicted_first"] == 1 and s["winners_scored"] == 2
    assert s["mean_podium_overlap"] == pytest.approx(1.5) and s["mean_chance_level_p_win"] == pytest.approx(0.1)
    assert summarise([]) == {"races": 0}


def test_calibration_table_bins_and_frequencies():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 4000)
    pairs = [(float(x), int(rng.random() < x)) for x in p]       # perfectly calibrated by construction
    table = calibration_table(pairs)
    assert sum(r["n"] for r in table) == 4000 and all(0 <= r["observed_rate"] <= 1 for r in table)
    assert all(abs(r["observed_rate"] - r["mean_predicted"]) < 0.08 for r in table if r["n"] > 200)
    assert all(a["high"] <= b["low"] + 1e-12 for a, b in zip(table, table[1:]))
    assert calibration_table([]) == []
    assert calibration_table([(1.0, 1)])[0]["mean_predicted"] == 1.0            # p == 1 lands in the last bin
