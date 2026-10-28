import numpy as np

from app.analytics.driver_metrics import pace_summary, teammate_delta
from app.analytics.tire_degradation import InsufficientDataError, fit_degradation
from app.data.ingestion import ingest_loaded_session
from app.ml.simulation import points_for_position, simulate_championship
from app.services.frames import session_laps_frame
from app.strategy.constraints import check_strategy
from app.strategy.simulator import simulate_strategy
from tests.conftest import make_fake_session

import pytest


def test_scoring():
    assert points_for_position(2024, 1) == 25
    assert points_for_position(2024, 10) == 1
    assert points_for_position(2024, 11) == 0
    assert points_for_position(2024, 1, sprint=True) == 8


def _sim(seed=0, remaining=5):
    drivers = ["A", "B", "C"]
    return simulate_championship(
        2024, drivers, {"A": "X", "B": "X", "C": "Y"}, {"A": 100, "B": 80, "C": 60}, {"X": 180, "Y": 60},
        {"A": 5.0, "B": 4.0, "C": 2.0}, remaining, n_sims=4000, seed=seed,
    )


def test_probabilities_sum_to_one_and_reproducible():
    r1, r2 = _sim(), _sim()
    assert abs(sum(r1.driver_win_prob.values()) - 1) < 1e-9
    assert abs(sum(r1.constructor_win_prob.values()) - 1) < 1e-9
    assert r1.driver_win_prob == r2.driver_win_prob
    assert r1.driver_win_prob["A"] > r1.driver_win_prob["C"]


def test_no_remaining_races_leader_wins():
    r = _sim(remaining=0)
    assert r.driver_win_prob["A"] == 1.0
    assert r.constructor_win_prob["X"] == 1.0


def test_stronger_team_favoured_and_drivers_feed_constructors():
    r = _sim()
    assert r.constructor_win_prob["X"] > r.constructor_win_prob["Y"]
    # X holds both title favourites, so its odds must be at least those of its best driver
    assert r.constructor_win_prob["X"] >= r.driver_win_prob["A"] - 0.05


def test_strategy_constraints():
    assert check_strategy(["MEDIUM", "HARD"], [20], 50) == []
    assert any("two different" in v for v in check_strategy(["MEDIUM", "MEDIUM"], [20], 50))
    assert check_strategy(["MEDIUM", "HARD"], [60], 50)
    assert check_strategy(["MEDIUM"], [], 50)


@pytest.fixture
def frame(db):
    ingest_loaded_session(db, make_fake_session(), 2024, "R")
    return session_laps_frame(db, 1)


def test_pace_and_teammate_delta(frame):
    p = pace_summary(frame)
    assert (p["clean_laps"] <= p["total_laps"]).all()
    assert p["delta_to_best_s"].min() == 0
    td = teammate_delta(frame)
    a, b = td.set_index("driver").loc["AAA", "delta_to_teammate_s"], td.set_index("driver").loc["BBB", "delta_to_teammate_s"]
    assert abs(a + b) < 1e-9 and a < 0


def test_degradation_recovers_synthetic_params(frame):
    from app.analytics.driver_metrics import clean_laps
    model = fit_degradation(clean_laps(frame))
    # Individual coefficients trade off (age, age^2 and the fuel proxy are correlated), so test the
    # identifiable quantity: net lap-time change over a 20-lap stint. Truth: 0.05*19 + 0.002*399 - 0.02*19 = 1.37
    net = model.lap_time("MEDIUM", 20, 20) - model.lap_time("MEDIUM", 1, 1)
    assert abs(net - 1.37) < 0.35
    assert model.resid_std < 0.5


def test_degradation_insufficient_data():
    import pandas as pd
    with pytest.raises(InsufficientDataError):
        fit_degradation(pd.DataFrame({"compound": ["SOFT"] * 3, "tyre_life": [1, 2, 3], "lap_number": [1, 2, 3], "lap_time_s": [90, 91, 92]}))


def test_simulate_strategy_identity_and_reproducible(frame):
    from app.analytics.driver_metrics import clean_laps
    model = fit_degradation(clean_laps(frame))
    actual = (["MEDIUM", "HARD"], [16])
    same = simulate_strategy(model, 40, 22.0, actual, actual, runs=500, seed=1)
    assert same.baseline_delta_s == 0
    alt = simulate_strategy(model, 40, 22.0, actual, (["MEDIUM", "HARD"], [24]), runs=500, seed=1)
    alt2 = simulate_strategy(model, 40, 22.0, actual, (["MEDIUM", "HARD"], [24]), runs=500, seed=1)
    assert alt.uncertainty_interval_s == alt2.uncertainty_interval_s
    lo, hi = alt.uncertainty_interval_s
    assert lo < hi and alt.warnings
    bad = simulate_strategy(model, 40, 22.0, actual, (["MEDIUM", "MEDIUM"], [18]), runs=500)
    assert bad.estimated_race_time_s is None and bad.constraint_violations


def test_profile_matches_the_headline_and_is_consistent(frame):
    from app.analytics.driver_metrics import clean_laps
    from app.strategy.simulator import strategy_profile
    model = fit_degradation(clean_laps(frame))
    actual = (["MEDIUM", "HARD"], [16])
    alt = (["MEDIUM", "HARD"], [24])
    res = simulate_strategy(model, 40, 22.0, actual, alt, runs=2000, seed=3)
    prof = res.profile
    assert [r["lap"] for r in prof] == list(range(1, 41))
    # the running difference ends exactly at the reported total, including both strategies' pit loss
    assert abs(prof[-1]["cumulative_delta_s"] - res.baseline_delta_s) < 1e-2
    # before either stop the strategies are identical, so there is no difference yet
    assert all(abs(r["cumulative_delta_s"]) < 1e-6 for r in prof[:15])
    # the actual strategy stops first (lap 16) and pays the 22 s pit loss, so the what-if is exactly 22 s ahead there
    assert abs(prof[16 - 1]["cumulative_delta_s"] + 22.0) < 1e-6
    # afterwards the actual car is on fresh tyres and claws time back, so the running difference rises
    assert prof[16]["cumulative_delta_s"] > prof[15]["cumulative_delta_s"]
    # the what-if pays its own stop at lap 24: a visible step of about the pit loss
    assert prof[23]["cumulative_delta_s"] - prof[22]["cumulative_delta_s"] > 15
    # band grows like sqrt(n) and its last value matches the reported 90% interval half-width closely
    assert prof[3]["band_s"] < prof[-1]["band_s"]
    lo, hi = res.uncertainty_interval_s
    assert abs(prof[-1]["band_s"] - (hi - lo) / 2) < 1.5
    assert res.actual_stints == [{"compound": "MEDIUM", "start_lap": 1, "end_lap": 16},
                                 {"compound": "HARD", "start_lap": 17, "end_lap": 40}]


def test_identical_strategies_have_a_flat_zero_profile(frame):
    from app.analytics.driver_metrics import clean_laps
    model = fit_degradation(clean_laps(frame))
    s = (["MEDIUM", "HARD"], [16])
    res = simulate_strategy(model, 40, 22.0, s, s, runs=200)
    assert all(r["cumulative_delta_s"] == 0 for r in res.profile)
    assert all(r["actual_pace_s"] == r["candidate_pace_s"] for r in res.profile)


def test_invalid_strategy_has_no_profile(frame):
    from app.analytics.driver_metrics import clean_laps
    model = fit_degradation(clean_laps(frame))
    bad = simulate_strategy(model, 40, 22.0, (["MEDIUM", "HARD"], [16]), (["MEDIUM", "MEDIUM"], [16]), runs=100)
    assert bad.profile == [] and bad.actual_stints == []
