import numpy as np
import pandas as pd

from app.analytics.pit_stop_analysis import (
    DEFAULT_PIT_LOSS_S, MIN_STOPS, estimate_pit_loss, estimate_pit_loss_detail, stop_losses,
)

TRUE_LOSS = 22.0


def race(stops, total=60, base=90.0, loss=TRUE_LOSS, shift_from=None, shift=0.0, status=None, compound="MEDIUM",
         seed=0):
    """Synthetic race. `stops` maps driver -> in-lap. In-lap costs 40% and out-lap 60% of `loss`."""
    rng = np.random.default_rng(seed)
    rows = []
    for d, pit in stops.items():
        for lap in range(1, total + 1):
            t = base + rng.normal(0, 0.15)
            if shift_from and lap >= shift_from:
                t += shift                      # conditions changed: every later lap is slower
            in_lap, out_lap = lap == pit, lap == pit + 1
            if in_lap:
                t += loss * 0.4
            if out_lap:
                t += loss * 0.6
            ts = "1"
            if status and (in_lap or out_lap):
                ts = status
            rows.append({"driver": d, "lap_number": lap, "lap_time_s": t, "is_valid": not (in_lap or out_lap),
                         "is_pit_lap": in_lap or out_lap, "neutralised": False, "track_status": ts,
                         "compound": compound})
    return pd.DataFrame(rows)


SIX = {f"D{i}": 15 + 3 * i for i in range(6)}


def test_clean_race_recovers_true_loss():
    r = estimate_pit_loss_detail(race(SIX))
    assert r.source == "measured" and r.warning is None and r.n_stops == 6
    assert abs(r.value - TRUE_LOSS) < 0.5


def test_local_baseline_survives_a_pace_shift_mid_race():
    # Stops straddle a +8 s pace change (e.g. a drying track). A whole-race median baseline is wrong for the
    # stops on the "minority" side of the shift; the local baseline is right for every stop.
    stops = {"A": 10, "B": 12, "C": 40, "D": 42, "E": 44, "F": 46}
    laps = race(stops, shift_from=28, shift=8.0)
    losses = stop_losses(laps)
    assert len(losses) == 6 and all(abs(x - TRUE_LOSS) < 1.5 for x in losses)
    base = laps[laps.is_valid].groupby("driver")["lap_time_s"].median()
    naive = [
        laps[(laps.driver == d) & laps.lap_number.isin([p, p + 1])]["lap_time_s"].sum() - 2 * base[d]
        for d, p in stops.items()
    ]
    assert max(abs(x - TRUE_LOSS) for x in naive) > 10   # the old approach got stops A and B wrong by ~16 s


def test_stops_under_neutralisation_are_skipped_and_a_default_is_used():
    for status in ("4", "6", "67", "5", "126"):
        r = estimate_pit_loss_detail(race(SIX, status=status))
        assert r.source == "default" and r.n_stops == 0 and r.value == DEFAULT_PIT_LOSS_S
        assert "clean dry pit stops" in r.warning


def test_yellow_flag_alone_does_not_exclude_a_stop():
    assert estimate_pit_loss_detail(race(SIX, status="12")).source == "measured"


def test_wet_tyres_are_excluded():
    for tyre in ("INTERMEDIATE", "WET"):
        assert estimate_pit_loss_detail(race(SIX, compound=tyre)).source == "default"
    assert estimate_pit_loss_detail(race(SIX, compound="hard")).source == "measured"  # case-insensitive


def test_too_few_stops_falls_back_with_a_warning():
    few = {f"D{i}": 20 + 5 * i for i in range(MIN_STOPS - 1)}
    r = estimate_pit_loss_detail(race(few))
    assert r.source == "default" and r.value == DEFAULT_PIT_LOSS_S and str(len(few)) in r.warning


def test_implausible_race_level_value_falls_back():
    r = estimate_pit_loss_detail(race(SIX, loss=45.0))
    assert r.source == "default" and "outside the plausible" in r.warning
    r = estimate_pit_loss_detail(race(SIX, loss=11.0))
    assert r.source == "default" and "outside the plausible" in r.warning


def test_inconsistent_stops_fall_back():
    laps = pd.concat([race({f"A{i}": 15 + 3 * i for i in range(4)}, loss=16.0),
                      race({f"B{i}": 15 + 3 * i for i in range(4)}, loss=33.0)])
    r = estimate_pit_loss_detail(laps)
    assert r.source == "default" and "vary too much" in r.warning and r.spread > 10


def test_single_artefacts_are_dropped_not_averaged_in():
    laps = race(SIX)
    mask = (laps.driver == "D0") & (laps.lap_number == 16)
    laps.loc[mask, "lap_time_s"] += 200            # a 200 s out-lap (e.g. a stop-go penalty / red flag)
    losses = stop_losses(laps)
    assert len(losses) == 5 and all(abs(x - TRUE_LOSS) < 1.5 for x in losses)


def test_lone_pit_lap_and_out_laps_are_not_counted_as_stops():
    laps = race({"A": 20})                                   # one real stop: in-lap 20, out-lap 21
    assert len(stop_losses(laps)) == 1
    laps.loc[(laps.driver == "A") & (laps.lap_number == 40), "is_pit_lap"] = True   # a lone flagged lap, no out-lap
    assert len(stop_losses(laps)) == 1                       # still just the real stop
    out_only = laps.copy()
    out_only["is_pit_lap"] = False
    out_only.loc[(out_only.driver == "A") & (out_only.lap_number == 30), "is_pit_lap"] = True
    assert stop_losses(out_only) == []


def test_wrapper_returns_value_and_warning_tuple():
    value, warning = estimate_pit_loss(race(SIX))
    assert abs(value - TRUE_LOSS) < 0.5 and warning is None
    value, warning = estimate_pit_loss(race({"A": 20}))
    assert value == DEFAULT_PIT_LOSS_S and warning
