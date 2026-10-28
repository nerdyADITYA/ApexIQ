import numpy as np
import pandas as pd
import pytest

from app.ml import race_backtest as rb
from app.ml.evaluation import form_strengths
from app.ml.race_model import (
    BASELINE, DNF_BOUNDS, ModelConfig, circuit_factor, dnf_probabilities, log_strengths, pace_ratings, predict_race,
    quali_ratings, race_grid_correlations, simulate_outcomes,
)

PTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def world(rounds=12, n_teams=6, seed=0, year_offset=0):
    """Synthetic season: team skill dominates, so pace and qualifying are informative and points are noisy."""
    rng = np.random.default_rng(seed)
    team_skill = np.linspace(2.0, 0.0, n_teams)
    drivers = [(f"T{t}D{k}", f"T{t}") for t in range(n_teams) for k in range(2)]
    rows = []
    for r in range(1, rounds + 1):
        perf = {d: team_skill[int(t[1:])] + rng.normal(0, 0.3) + rng.gumbel() * 0.8 for d, t in drivers}
        order = sorted(perf, key=lambda d: -perf[d])
        dnfs = {d for d in order if rng.random() < 0.06}
        classified = [d for d in order if d not in dnfs] + [d for d in order if d in dnfs]
        quali = {d: i + 1 for i, d in enumerate(sorted(perf, key=lambda d: -(perf[d] + rng.normal(0, 0.5))))}
        for pos, d in enumerate(classified, 1):
            t = dict(drivers)[d]
            rows.append({"round": r, "driver": d, "team": t, "circuit": f"C{r % 4}", "finish": pos, "grid": quali[d], "status": "Retired" if d in dnfs else "Finished",
                         "race_points": float(PTS[pos - 1]) if pos <= 10 and d not in dnfs else 0.0, "sprint_points": 0.0,
                         "quali_pos": quali[d], "pace_pct": float(-1.2 * (perf[d] - 1.0) + rng.normal(0, 0.15)),
                         "dnf": d in dnfs})
    return pd.DataFrame(rows)


def test_baseline_config_is_exactly_the_points_form_model():
    h = world()
    drivers = sorted(h["driver"].unique())
    teams = dict(zip(h["driver"], h["team"]))
    raw = form_strengths(h, decay=1.0)
    expected = 2.5 * np.log(np.array([raw[d] for d in drivers]))
    assert np.allclose(log_strengths(h, drivers, teams, BASELINE), expected)


def test_pace_rating_orders_teams_shrinks_and_is_shared_within_a_team():
    h = world(rounds=10)
    drivers = sorted(h["driver"].unique())
    teams = dict(zip(h["driver"], h["team"]))
    cfg = ModelConfig("x", beta=1.0)
    pr = pace_ratings(h, drivers, teams, cfg)
    assert pr["T0D0"] < pr["T3D0"] < pr["T5D0"]                      # negative = faster
    # teammates end up closer together than with team sharing switched off (same weighting and shrinkage)
    alone = pace_ratings(h, drivers, teams, ModelConfig("x", beta=1.0, team_share=0.0))
    assert abs(pr["T2D0"] - pr["T2D1"]) < abs(alone["T2D0"] - alone["T2D1"])
    assert abs(pr["T2D0"] - pr["T2D1"]) == pytest.approx(0.5 * abs(alone["T2D0"] - alone["T2D1"]), rel=1e-6)
    # shrinkage: with a single race the rating is pulled toward 0
    one = pace_ratings(h[h["round"] == 1], drivers, teams, ModelConfig("x", beta=1.0, team_share=0.0))
    full_single = h[h["round"] == 1].set_index("driver")["pace_pct"]
    assert all(abs(one[d]) < abs(full_single[d]) for d in drivers)       # pulled toward the field (0)
    # unseen driver inherits the team rating
    unseen = pace_ratings(h, drivers + ["NEW"], {**teams, "NEW": "T0"}, cfg)["NEW"]
    t0_mean = np.mean([pr["T0D0"], pr["T0D1"]])
    assert abs(unseen - t0_mean) < 0.3


def test_quali_rating_negative_for_better_qualifiers():
    h = world(rounds=10)
    drivers = sorted(h["driver"].unique())
    qr = quali_ratings(h, drivers, ModelConfig("x", gamma=0.1))
    assert qr["T0D0"] < 0 < qr["T5D1"]


def test_pace_and_quali_terms_raise_strength_of_faster_drivers():
    h = world(rounds=10)
    drivers = sorted(h["driver"].unique())
    teams = dict(zip(h["driver"], h["team"]))
    base = log_strengths(h, drivers, teams, ModelConfig("b", alpha=0.0))
    with_pace = log_strengths(h, drivers, teams, ModelConfig("p", alpha=0.0, beta=2.0))
    assert np.allclose(base, 0.0)                                      # nothing but pace and quali can differentiate
    i, j = drivers.index("T0D0"), drivers.index("T5D0")
    assert with_pace[i] > with_pace[j]


def test_dnf_probabilities_shrink_clip_and_fixed_mode():
    h = world(rounds=30, seed=3)
    drivers = sorted(h["driver"].unique())
    teams = dict(zip(h["driver"], h["team"]))
    assert np.allclose(dnf_probabilities(h, drivers, teams, BASELINE), 0.05)
    shrunk = dnf_probabilities(h, drivers, teams, ModelConfig("s", dnf_mode="shrunk"))
    assert (shrunk >= DNF_BOUNDS[0]).all() and (shrunk <= DNF_BOUNDS[1]).all()
    # a driver who retires in every race is pushed up but not to certainty, thanks to shrinkage
    crash = h.copy()
    crash.loc[crash["driver"] == "T0D0", "dnf"] = True
    p = dnf_probabilities(crash, drivers, teams, ModelConfig("s", dnf_mode="shrunk"))
    assert p[drivers.index("T0D0")] > shrunk[drivers.index("T0D0")] and p[drivers.index("T0D0")] <= DNF_BOUNDS[1]
    # no history -> fixed value
    assert np.allclose(dnf_probabilities(h.iloc[0:0], drivers, teams, ModelConfig("s", dnf_mode="shrunk")), 0.05)


def test_simulation_accounts_for_every_outcome_and_is_seeded():
    log_s = np.log(np.array([5.0, 3.0, 1.0, 1.0]))
    a = simulate_outcomes(log_s, np.full(4, 0.05), 5000, seed=1)
    b = simulate_outcomes(log_s, np.full(4, 0.05), 5000, seed=1)
    assert np.allclose(a["pos_prob"], b["pos_prob"])
    assert np.allclose(a["pos_prob"].sum(axis=1) + a["p_dnf"], 1.0, atol=1e-9)
    assert a["expected_position"][0] < a["expected_position"][3]


def test_predict_race_shapes():
    h = world()
    lineup = dict(zip(h["driver"], h["team"]))
    out = predict_race(h, h, lineup, ModelConfig("m", beta=1.0, dnf_mode="shrunk"), n_sims=3000)
    assert out["drivers"] == sorted(lineup) and out["pos_prob"].shape == (12, 12)
    assert out["p_win"].sum() > 0.97 and (out["p_win"] <= out["p_podium"] + 1e-12).all()


CONFIGS = [BASELINE, ModelConfig("pace", beta=1.0), ModelConfig("pace+quali", beta=1.0, gamma=0.05, dnf_mode="shrunk")]  # beta ~1 is calibrated for this synthetic noise level


@pytest.fixture(scope="module")
def pred():
    hist = {2024: world(14, seed=1), 2025: world(14, seed=2)}
    return rb.collect(hist, CONFIGS, n_sims=1500)


def test_collect_covers_every_config_and_baseline_ranker(pred):
    assert set(pred["config"]) == {"baseline", "pace", "pace+quali", "uniform", "last race result", "championship order"}
    one = pred[(pred["config"] == "baseline") & (pred["year"] == 2025)]
    assert sorted(one["round"].unique()) == list(range(5, 15))            # first 4 rounds are warm-up only
    assert pred[pred["config"] == "last race result"]["p_win"].isna().all()


def test_no_future_information_leaks_into_earlier_predictions():
    hist = {2025: world(10, seed=5)}
    base = rb.collect(hist, [CONFIGS[1]], n_sims=1000, rankers=())
    tampered = {2025: hist[2025].copy()}
    late = tampered[2025]["round"] >= 8
    tampered[2025].loc[late, "pace_pct"] = 50.0
    tampered[2025].loc[late, "finish"] = tampered[2025].loc[late, "finish"].iloc[::-1].to_numpy()
    after = rb.collect(tampered, [CONFIGS[1]], n_sims=1000, rankers=())
    for r in (5, 6, 7, 8):   # round 8's own result changed, but its prediction may only use rounds < 8
        a = base[(base["round"] == r) & (base["config"] == "pace")].sort_values("driver")["p_podium"].to_numpy()
        b = after[(after["round"] == r) & (after["config"] == "pace")].sort_values("driver")["p_podium"].to_numpy()
        assert np.allclose(a, b)


def test_scores_are_sensible_and_informative_models_beat_the_baselines(pred):
    scores = rb.race_scores(pred)
    mean = scores.groupby("config")[["spearman", "mae"]].mean()
    assert mean.loc["uniform", "spearman"] == pytest.approx(0.0)
    assert mean.loc["pace", "spearman"] > mean.loc["uniform", "spearman"] + 0.2
    assert mean.loc["pace", "mae"] < mean.loc["uniform", "mae"]
    assert rb.pooled_probability_loss(scores, "pace") < rb.pooled_probability_loss(scores, "uniform")
    # which model wins is an empirical question (see the real backtest); here just check the paired comparison runs
    d = rb.paired_difference(scores, "pace", "baseline", "ll_top10", n_boot=300)
    assert d["n_races"] == 20 and d["low"] <= d["mean"] <= d["high"]


def test_paired_difference_sign_and_interval():
    rows = [{"config": c, "year": 2025, "round": r, "ll_top10": base + (0.0 if c == "b" else -1.0) + 0.01 * (r % 3)}
            for r in range(5, 25) for c, base in (("a", 2.0), ("b", 2.0))]
    d = rb.paired_difference(pd.DataFrame(rows), "a", "b", "ll_top10", n_boot=300)
    assert d["mean"] == pytest.approx(-1.0) and d["high"] < -0.99 and d["n_races"] == 20


def test_perfect_and_reversed_predictors_score_plus_and_minus_one():
    base = pd.DataFrame({"config": "m", "year": 2025, "round": 5, "driver": list("ABCDE"), "finish": [1, 2, 3, 4, 5],
                         "dnf": False, "p_win": 0.2, "p_podium": 0.6, "p_top10": 1.0, "p_dnf": 0.05})
    perfect = base.assign(exp_pos=[1, 2, 3, 4, 5])
    reversed_ = base.assign(exp_pos=[5, 4, 3, 2, 1])
    assert rb.race_scores(perfect)["spearman"].iloc[0] == pytest.approx(1.0)
    assert rb.race_scores(reversed_)["spearman"].iloc[0] == pytest.approx(-1.0)
    assert rb.race_scores(perfect)["mae"].iloc[0] == 0.0
    assert rb.race_scores(reversed_)["mae"].iloc[0] == pytest.approx(2.4)


# ---- grid (post-qualifying) model ---------------------------------------------------------------------------------

def _grid_inputs():
    h = world(rounds=8)
    drivers = sorted(h["driver"].unique())
    teams = dict(zip(h["driver"], h["team"]))
    return h, drivers, teams


def test_grid_term_favours_the_front_and_is_off_without_delta_or_grid():
    h, drivers, teams = _grid_inputs()
    grid = {d: i + 1 for i, d in enumerate(drivers)}
    flat = log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0))
    with_grid = log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=1.0), grid)
    assert np.allclose(flat, 0.0)
    assert with_grid[0] > with_grid[5] > with_grid[-1]                     # pole beats mid-grid beats the back
    assert with_grid[0] == pytest.approx(0.0) and with_grid[-1] == pytest.approx(-np.log(len(drivers)))
    assert np.allclose(log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=0.0), grid), 0.0)
    assert np.allclose(log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=1.0), None), 0.0)


def test_missing_grid_slot_is_treated_as_starting_at_the_back():
    h, drivers, teams = _grid_inputs()
    grid = {d: i + 1 for i, d in enumerate(drivers)}
    grid[drivers[0]] = float("nan")
    out = log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=1.0), grid)
    assert out[0] == pytest.approx(-np.log(len(drivers)))


def test_circuit_factor_scales_the_grid_weight_only_when_kappa_is_set():
    h, drivers, teams = _grid_inputs()
    grid = {d: i + 1 for i, d in enumerate(drivers)}
    base = log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=1.0, kappa=0.0), grid, circuit_factor=1.4)
    scaled = log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=1.0, kappa=1.0), grid, circuit_factor=1.4)
    assert np.allclose(base, log_strengths(h, drivers, teams, ModelConfig("g", alpha=0.0, delta=1.0), grid))   # kappa 0: no effect
    assert np.allclose(scaled, 1.4 * base)


def test_grid_correlation_and_circuit_factor():
    rows = []
    for year, rnd, circuit, rev in [(2024, 1, "Easy", True), (2024, 2, "Proc", False), (2024, 3, "Proc", False), (2024, 4, "Mid", False)]:
        for i in range(1, 13):
            rows.append({"year": year, "round": rnd, "circuit": circuit, "quali_pos": i, "finish": 13 - i if rev else i})
    corr = race_grid_correlations(pd.DataFrame(rows))
    assert corr.set_index(["round"])["rho"].round(2).to_dict() == {1: -1.0, 2: 1.0, 3: 1.0, 4: 1.0}
    assert circuit_factor(corr.iloc[0:0], "Proc") == 1.0 and circuit_factor(corr, None) == 1.0
    assert circuit_factor(corr, "Unseen") == 1.0                                    # no history here: average
    assert circuit_factor(corr, "Proc") > 1.0 > circuit_factor(corr, "Easy")        # processional vs overtaking-friendly
    assert 0.5 <= circuit_factor(corr, "Easy") and circuit_factor(corr, "Proc") <= 1.5
    # shrinkage: the same circuit with more past visits is trusted more, so its factor moves further from 1
    def table(visits):
        r = [{"year": 2020 + i, "round": 1, "circuit": "X", "rho": 0.9} for i in range(visits)]
        r += [{"year": 2020 + i, "round": 2 + j, "circuit": f"O{j}", "rho": 0.5} for i in range(4) for j in range(3)]
        return pd.DataFrame(r)
    f1, f4 = circuit_factor(table(1), "X"), circuit_factor(table(4), "X")
    assert 1.0 < f1 < f4 <= 1.5
    assert race_grid_correlations(pd.DataFrame(rows).head(5)).empty                 # too few drivers to correlate


GRID_CFGS = [ModelConfig("pre", alpha=2.5), ModelConfig("grid", alpha=1.5, delta=1.0), ModelConfig("grid+circuit", alpha=1.5, delta=1.0, kappa=1.0)]


def test_grid_models_use_qualifying_but_never_the_races_own_result():
    hist = {2024: world(8, seed=1), 2025: world(10, seed=2)}
    base = rb.collect(hist, GRID_CFGS, n_sims=1000, rankers=(), years=[2025], need_grid=True)
    # change the finishing results of round 8 (the race being predicted): predictions must not move
    t1 = {y: h.copy() for y, h in hist.items()}
    m = (t1[2025]["round"] == 8)
    t1[2025].loc[m, "finish"] = t1[2025].loc[m, "finish"].iloc[::-1].to_numpy()
    t1[2025].loc[m, "pace_pct"] = 99.0
    after = rb.collect(t1, GRID_CFGS, n_sims=1000, rankers=(), years=[2025], need_grid=True)
    pick = lambda df, c: df[(df["round"] == 8) & (df["config"] == c)].sort_values("driver")["p_podium"].to_numpy()  # noqa: E731
    for c in ("pre", "grid", "grid+circuit"):
        assert np.allclose(pick(base, c), pick(after, c))
    # but changing that race's own qualifying order DOES change a grid model (and not the pre-qualifying one)
    t2 = {y: h.copy() for y, h in hist.items()}
    m = (t2[2025]["round"] == 8)
    t2[2025].loc[m, "quali_pos"] = (21 - t2[2025].loc[m, "quali_pos"]).to_numpy()
    moved = rb.collect(t2, GRID_CFGS, n_sims=1000, rankers=(), years=[2025], need_grid=True)
    assert not np.allclose(pick(base, "grid"), pick(moved, "grid"))
    assert np.allclose(pick(base, "pre"), pick(moved, "pre"))


def test_races_without_qualifying_are_skipped_when_a_grid_is_required():
    hist = {2025: world(8, seed=3)}
    hist[2025].loc[hist[2025]["round"] == 6, "quali_pos"] = np.nan
    pred = rb.collect(hist, GRID_CFGS[:2], n_sims=500, rankers=(), need_grid=True)
    assert 6 not in set(pred["round"]) and {5, 7, 8} <= set(pred["round"])
    assert 6 in set(rb.collect(hist, GRID_CFGS[:1], n_sims=500, rankers=())["round"])    # kept when not required


def test_grid_order_baseline_and_informative_grid_model():
    hist = {2024: world(10, seed=1), 2025: world(12, seed=2)}
    pred = rb.collect(hist, GRID_CFGS[:2], n_sims=1500, rankers=(rb.GRID_RANKER,), need_grid=True)
    scores = rb.race_scores(pred)
    mean = scores.groupby("config")["spearman"].mean()
    assert mean[rb.GRID_RANKER] > 0.5                                    # in this world the grid tells a lot
    assert mean["grid"] > mean["pre"] + 0.05                             # and a model that uses it beats one that cannot


# ---- team x circuit effect -----------------------------------------------------------------------------------------

from app.ml.features import canonical_team, team_circuit_deltas  # noqa: E402


def circuit_season(year_seed, fast_team="T0", visits_at_x=1, boost=1.0):
    """A season where `fast_team` is `boost` % faster than usual (lower pace_pct) at circuit X, equal elsewhere."""
    rng = np.random.default_rng(year_seed)
    rows = []
    for r in range(1, 9):
        circuit = "X" if r <= visits_at_x else f"C{r}"
        for t in range(5):
            for k in range(2):
                pace = -1.0 * (2 - t * 0.5) + rng.normal(0, 0.05)
                if circuit == "X" and f"T{t}" == fast_team:
                    pace -= boost
                rows.append({"round": r, "circuit": circuit, "team": f"T{t}", "driver": f"T{t}D{k}", "pace_pct": pace})
    return pd.DataFrame(rows)


def test_team_circuit_delta_finds_the_team_that_goes_well_at_a_circuit():
    d = team_circuit_deltas([circuit_season(1)], "X")
    assert d["T0"] < -0.15 and all(abs(d[t]) < abs(d["T0"]) for t in d if t != "T0")   # one visit: shrunk hard
    assert team_circuit_deltas([circuit_season(1)], "Nowhere") == {} and team_circuit_deltas([circuit_season(1)], None) == {}
    assert team_circuit_deltas([], "X") == {}


def test_more_visits_are_trusted_more_but_never_fully():
    one = team_circuit_deltas([circuit_season(1)], "X")["T0"]
    three = team_circuit_deltas([circuit_season(1), circuit_season(2), circuit_season(3)], "X")["T0"]
    assert three < one < 0                       # more evidence: further from zero
    assert abs(three) < 1.0                      # shrunk: never reaches the raw +/-1% effect


def test_team_renames_are_followed_across_seasons():
    old = circuit_season(1, fast_team="T0")
    old["team"] = old["team"].replace({"T0": "AlphaTauri"})
    new = circuit_season(2, fast_team="T0")
    new["team"] = new["team"].replace({"T0": "Racing Bulls"})
    assert canonical_team("AlphaTauri") == canonical_team("RB") == "Racing Bulls" == canonical_team("Racing Bulls")
    merged = team_circuit_deltas([old, new], "X")
    assert set(merged) >= {"Racing Bulls"} and "AlphaTauri" not in merged


def test_epsilon_moves_strength_toward_teams_that_suit_the_circuit_and_is_off_by_default():
    h = world(rounds=6)
    drivers = sorted(h["driver"].unique())
    teams = dict(zip(h["driver"], h["team"]))
    delta = {"T0": -1.0, "T5": 1.0}
    off = log_strengths(h, drivers, teams, ModelConfig("x", alpha=0.0, epsilon=0.0), circuit_delta=delta)
    on = log_strengths(h, drivers, teams, ModelConfig("x", alpha=0.0, epsilon=2.0), circuit_delta=delta)
    assert np.allclose(off, 0.0)
    i, j, k = drivers.index("T0D0"), drivers.index("T5D0"), drivers.index("T2D0")
    assert on[i] == pytest.approx(2.0) and on[j] == pytest.approx(-2.0) and on[k] == pytest.approx(0.0)
    assert np.allclose(log_strengths(h, drivers, teams, ModelConfig("x", alpha=0.0, epsilon=2.0), circuit_delta=None), 0.0)


def test_circuit_effect_uses_only_earlier_seasons():
    hist = {2023: circuit_season(1), 2024: circuit_season(2), 2025: world(10, seed=4)}
    for y in (2023, 2024):
        hist[y] = hist[y].assign(finish=lambda d: d.groupby("round").cumcount() + 1, grid=1, status="Finished", race_points=0.0,
                                 sprint_points=0.0, quali_pos=1, dnf=False)
    cfgs = [ModelConfig("circ", alpha=1.0, epsilon=2.0)]
    base = rb.collect({k: v.copy() for k, v in hist.items()}, cfgs, n_sims=800, rankers=(), years=[2025], min_train_rounds=2)
    t = {k: v.copy() for k, v in hist.items()}
    t[2025].loc[t[2025]["round"] >= 4, "pace_pct"] = 99.0           # change this season's own (and later) pace
    after = rb.collect(t, cfgs, n_sims=800, rankers=(), years=[2025], min_train_rounds=2)
    pick = lambda df: df[(df["round"] == 4) & (df["config"] == "circ")].sort_values("driver")["p_podium"].to_numpy()  # noqa: E731
    assert np.allclose(pick(base), pick(after))
