import numpy as np
import pandas as pd

from app.ml import evaluation as ev


def make_results(n_rounds=10, seed=0):
    rng = np.random.default_rng(seed)
    drivers = [f"D{i}" for i in range(20)]  # 20 drivers so "top 10" is not trivially true
    skill = np.linspace(4.0, 0.0, 20)  # clearly separated drivers, so a form model should beat uniform
    pts_table = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1] + [0] * 10
    rows = []
    for r in range(1, n_rounds + 1):
        order = np.argsort(-(skill + rng.gumbel(size=20)))
        for pos, i in enumerate(order, 1):
            rows.append({"round": r, "driver": drivers[i], "team": f"T{i // 2}", "finish": pos,
                         "race_points": float(pts_table[pos - 1]), "sprint_points": 0.0})
    return pd.DataFrame(rows)


def test_no_future_leakage_in_predictions():
    """Changing results of rounds >= r must not change predictions for round r."""
    res = make_results()
    base = ev.backtest_races(res, min_train_rounds=4, n_sims=500)
    tampered = res.copy()
    late = tampered["round"] >= 7
    tampered.loc[late, "race_points"] = 999.0
    tampered.loc[late, "finish"] = tampered.loc[late, "finish"].iloc[::-1].to_numpy()
    after = ev.backtest_races(tampered, min_train_rounds=4, n_sims=500)
    for r in (5, 6, 7):  # round 7's own result changed, but its prediction may only use rounds < 7
        a = base[base["round"] == r].sort_values(["model", "target", "driver"])["p"].to_numpy()
        b = after[after["round"] == r].sort_values(["model", "target", "driver"])["p"].to_numpy()
        assert np.allclose(a, b), f"round {r} predictions changed with future data"


def test_form_strengths_use_only_given_history():
    res = make_results()
    s1 = ev.form_strengths(res[res["round"] <= 5], 1.0)
    res2 = res.copy()
    res2.loc[res2["round"] > 5, "race_points"] = 1000.0
    assert s1 == ev.form_strengths(res2[res2["round"] <= 5], 1.0)


def test_probability_sanity():
    p = ev.race_probabilities({"A": 5.0, "B": 3.0, "C": 1.0}, ["A", "B", "C"], n_sims=4000)
    assert p["win"].is_monotonic_decreasing
    assert (p["podium"] <= 1).all() and p.loc["A", "win"] > p.loc["C", "win"]


def test_metrics_known_values():
    assert abs(ev.log_loss([1, 0], [0.5, 0.5]) - np.log(2)) < 1e-9
    assert ev.brier([1, 0], [1.0, 0.0]) == 0.0


def test_skilled_model_beats_uniform_on_skewed_data():
    res = make_results(n_rounds=16)
    s = ev.summarise(ev.backtest_races(res, n_sims=1000), n_boot=200)
    for target in ("podium", "top10"):
        row = s[(s["target"] == target) & (s["model"] == "season-form (decay 1.0)")].iloc[0]
        assert row["gain_vs_uniform"] > 0


def test_reproducible():
    res = make_results()
    a = ev.backtest_races(res, n_sims=500, seed=3)
    b = ev.backtest_races(res, n_sims=500, seed=3)
    assert a.equals(b)


def test_sharpening_selection_ignores_future_rounds():
    res = make_results(n_rounds=10)
    base, chosen = ev.backtest_sharpened(res, alphas=(1.0, 2.0, 3.0), n_sims=400)
    tampered = res.copy()
    late = tampered["round"] >= 8
    tampered.loc[late, "finish"] = 21 - tampered.loc[late, "finish"]   # reverse the order in late rounds
    tampered.loc[late, "race_points"] = 0.0
    after, chosen2 = ev.backtest_sharpened(tampered, alphas=(1.0, 2.0, 3.0), n_sims=400)
    # alpha for round r may depend on outcomes of rounds < r only
    assert chosen[chosen["round"] <= 8]["alpha"].tolist() == chosen2[chosen2["round"] <= 8]["alpha"].tolist()
    a = base[base["round"] <= 7].sort_values(["target", "driver", "round"])["p"].to_numpy()
    b = after[after["round"] <= 7].sort_values(["target", "driver", "round"])["p"].to_numpy()
    assert np.allclose(a, b)


def test_sharpen_spreads_probabilities():
    s = {"A": 5.0, "B": 3.0, "C": 1.0}
    flat = ev.race_probabilities(s, list(s), n_sims=6000, sharpen=1.0)
    sharp = ev.race_probabilities(s, list(s), n_sims=6000, sharpen=3.0)
    assert sharp.loc["A", "win"] > flat.loc["A", "win"] and sharp.loc["C", "win"] < flat.loc["C", "win"]
