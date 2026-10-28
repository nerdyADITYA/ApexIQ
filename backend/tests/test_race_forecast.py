import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.data.ingestion import ingest_loaded_session, upsert_schedule
from app.main import app
from app.ml.race_forecast import MODEL_VERSION, ForecastError, forecast_race
from tests.conftest import make_fake_session

PTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def history(rounds=(1, 2, 3), n=10, strong_first=True):
    """n drivers; D0 strongest. Results in round order of skill with some shuffling."""
    rng = np.random.default_rng(0)
    rows = []
    for r in rounds:
        order = np.argsort(-(np.linspace(3, 0, n) + rng.gumbel(size=n)))
        for pos, i in enumerate(order, 1):
            rows.append({"round": r, "driver": f"D{i}", "team": f"T{i // 2}", "finish": pos,
                         "race_points": float(PTS[pos - 1]) if pos <= 10 else 0.0, "sprint_points": 0.0})
    return pd.DataFrame(rows)


def test_probability_structure():
    f = forecast_race(history(), 2026, n_sims=4000)
    n = f["positions"]
    assert n == 10 and f["model_version"] == MODEL_VERSION and f["mode"] == "pre-qualifying"
    cols = np.zeros(n)
    for d in f["drivers"]:
        pp = np.array(d["position_probs"])
        assert len(pp) == n and abs(pp.sum() + d["p_dnf"] - 1) < 2e-3          # every outcome is accounted for
        assert d["p_win"] <= d["p_podium"] <= d["p_points"] + 1e-9 and 0 <= d["p_dnf"] <= 1
        cols += pp
    assert (cols <= 1 + 1e-3).all() and cols[0] > 0.97                            # one winner unless all 10 retire
    assert sum(d["p_win"] for d in f["drivers"]) > 0.97
    # expected points cannot exceed the points available in a race
    assert 0 < sum(d["expected_points"] for d in f["drivers"]) <= 101


def test_stronger_driver_ranks_higher_and_table_is_sorted():
    f = forecast_race(history(rounds=range(1, 9)), 2026, n_sims=6000)
    ds = f["drivers"]
    assert [d["predicted_rank"] for d in ds] == list(range(1, 11))
    assert [d["expected_position"] for d in ds] == sorted(d["expected_position"] for d in ds)
    best, worst = ds[0], ds[-1]
    assert best["p_win"] > worst["p_win"] and best["expected_points"] > worst["expected_points"]


def test_reproducible_with_a_seed_and_seed_changes_noise_only():
    a = forecast_race(history(), 2026, n_sims=3000, seed=5)["drivers"]
    b = forecast_race(history(), 2026, n_sims=3000, seed=5)["drivers"]
    c = forecast_race(history(), 2026, n_sims=3000, seed=6)["drivers"]
    assert [x["position_probs"] for x in a] == [x["position_probs"] for x in b]
    assert [x["position_probs"] for x in a] != [x["position_probs"] for x in c]
    assert abs(a[0]["p_win"] - next(x for x in c if x["driver"] == a[0]["driver"])["p_win"]) < 0.05


def test_empty_history_raises_a_user_safe_error():
    with pytest.raises(ForecastError, match="No completed races"):
        forecast_race(history().iloc[0:0], 2026)


def test_lineup_comes_from_latest_race_with_notes_and_unseen_drivers():
    h = history(rounds=(1, 2))
    h = pd.concat([h, pd.DataFrame([{"round": 1, "driver": "GONE", "team": "T9", "finish": 11,
                                     "race_points": 0.0, "sprint_points": 0.0}])])
    new_in_last = pd.DataFrame([{"round": 2, "driver": "ROOKIE", "team": "T9", "finish": 11,
                                 "race_points": 0.0, "sprint_points": 0.0}])
    h = pd.concat([h, new_in_last])
    f = forecast_race(h, 2026, n_sims=2000)
    codes = {d["driver"] for d in f["drivers"]}
    assert "GONE" not in codes and "ROOKIE" in codes and f["lineup_from_round"] == 2
    assert [n["driver"] for n in f["lineup_notes"]] == ["GONE"] and "not in the latest race" in f["lineup_notes"][0]["note"]
    assert next(d for d in f["drivers"] if d["driver"] == "ROOKIE")["has_history"] is True   # a 0-point result is a result


def test_constructor_points_are_the_sum_of_their_drivers():
    f = forecast_race(history(), 2026, n_sims=3000)
    by_team = {}
    for d in f["drivers"]:
        by_team[d["team"]] = by_team.get(d["team"], 0) + d["expected_points"]
    for c in f["constructors"]:
        assert abs(c["expected_points"] - by_team[c["team"]]) < 0.02


@pytest.fixture
def client(db):
    for rnd in (1, 2):
        ingest_loaded_session(db, make_fake_session(seed=rnd, round_number=rnd), 2024, "R")
    schedule = pd.DataFrame([
        {"RoundNumber": r, "EventName": f"Future GP {r}" if r > 2 else "Test GP", "Location": "Testville" if r <= 3 else "Newtown",
         "Country": "Nowhere", "EventDate": pd.Timestamp("2024-06-01") + pd.Timedelta(days=7 * r)} for r in (1, 2, 3, 4)])
    upsert_schedule(db, 2024, schedule)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upcoming_list(client):
    r = client.get("/api/v1/predictions/2024").json()
    assert r["completed_rounds"] == 2 and [u["round"] for u in r["upcoming"]] == [3, 4]
    u3, u4 = r["upcoming"]
    assert u3["circuit_history_seasons"] == 0 and u3["forecastable"] and u3["qualifying_available"] is False
    assert u3["date"] == "2024-06-22"
    assert client.get("/api/v1/predictions/1999").status_code == 404


def test_race_forecast_endpoint(client):
    r = client.get("/api/v1/predictions/2024/rounds/3", params={"n_sims": 2000}).json()
    assert r["race"]["round"] == 3 and r["race"]["event"] == "Future GP 3" and r["as_of_round"] == 2
    assert {d["driver"] for d in r["drivers"]} == {"AAA", "BBB", "CCC", "DDD"}
    assert all(d["name"] for d in r["drivers"]) and r["caveats"] and r["generated_at"]
    # later upcoming rounds use the same data as of the last completed race
    assert client.get("/api/v1/predictions/2024/rounds/4", params={"n_sims": 2000}).json()["as_of_round"] == 2


def test_forecast_errors(client):
    assert client.get("/api/v1/predictions/2024/rounds/1").status_code == 409      # already raced
    assert client.get("/api/v1/predictions/2024/rounds/99").status_code == 404
    assert client.get("/api/v1/predictions/2024/rounds/3", params={"n_sims": 10}).status_code == 422
    assert client.get("/api/v1/predictions/1999/rounds/1").status_code == 404


def test_retirement_chances_come_from_driver_and_team_history_and_are_bounded():
    rows = []
    rng = np.random.default_rng(1)
    for _ in range(25):                                          # 25 earlier starts for every driver
        for i in range(10):
            team = f"T{i // 2}"
            p = 0.6 if team == "T0" else 0.02                    # team T0 is very unreliable
            rows.append({"driver": f"D{i}", "team": team, "dnf": bool(rng.random() < p)})
    f = forecast_race(history(), 2026, n_sims=3000, dnf_history=pd.DataFrame(rows))
    dnf = {d["driver"]: d["p_dnf"] for d in f["drivers"]}
    assert min(dnf[d] for d in ("D0", "D1")) > 3 * max(dnf[d] for d in ("D4", "D5", "D6", "D7"))
    assert max(dnf.values()) <= 0.40 + 0.02                      # clipped (plus simulation noise), not 60%
    assert len({round(v, 2) for v in dnf.values()}) > 1          # no longer one fixed number for everyone
    assert any("per driver and team" in c for c in f["caveats"])


def test_without_retirement_history_the_old_fixed_rate_is_used():
    f = forecast_race(history(), 2026, n_sims=4000)             # history frame has no dnf column
    assert all(abs(d["p_dnf"] - 0.05) < 0.02 for d in f["drivers"])


# ---- post-qualifying mode ------------------------------------------------------------------------------------------

def _quali(order):
    return {d: (float(i + 1), f"T{int(d[1:]) // 2}") for i, d in enumerate(order)}


def test_post_qualifying_uses_the_grid_and_changes_the_odds():
    h = history(rounds=range(1, 8))
    pre = forecast_race(h, 2026, n_sims=6000)
    weakest = pre["drivers"][-1]["driver"]                          # worst form on pole, best form at the back
    strongest = pre["drivers"][0]["driver"]
    others = [d["driver"] for d in pre["drivers"] if d["driver"] not in (weakest, strongest)]
    q = _quali([weakest, *others, strongest])
    post = forecast_race(h, 2026, n_sims=6000, quali=q)
    assert pre["mode"] == "pre-qualifying" and post["mode"] == "post-qualifying"
    assert post["model_version"] != pre["model_version"] and "qualifying order is used as the starting grid" in post["caveats"][0]
    by = {d["driver"]: d for d in post["drivers"]}
    assert by[weakest]["grid"] == 1 and by[strongest]["grid"] == 10 and all(d["grid"] for d in post["drivers"])
    pre_by = {d["driver"]: d for d in pre["drivers"]}
    assert by[weakest]["p_win"] > 5 * pre_by[weakest]["p_win"]       # pole matters a lot
    assert by[strongest]["p_win"] < pre_by[strongest]["p_win"]       # starting last costs the best car
    assert pre_by[weakest]["grid"] is None


def test_post_qualifying_entrants_come_from_qualifying_and_gaps_are_noted():
    h = history(rounds=range(1, 6))
    order = [f"D{i}" for i in range(10)]
    q = _quali(order[:9])                                           # D9 has no qualifying result
    f = forecast_race(h, 2026, n_sims=2000, quali=q)
    assert {d["driver"] for d in f["drivers"]} == set(order[:9]) and f["positions"] == 9
    assert any(n["driver"] == "D9" and "no qualifying result" in n["note"] for n in f["lineup_notes"])


def test_partial_qualifying_falls_back_to_the_pre_qualifying_model():
    h = history(rounds=range(1, 6))
    f = forecast_race(h, 2026, n_sims=2000, quali=_quali([f"D{i}" for i in range(5)]))   # only half the field
    assert f["mode"] == "pre-qualifying" and all(d["grid"] is None for d in f["drivers"])
    assert forecast_race(h, 2026, n_sims=2000, quali={})["mode"] == "pre-qualifying"


def test_endpoint_switches_to_post_qualifying_when_qualifying_is_ingested(client, db):
    pre = client.get("/api/v1/predictions/2024/rounds/3", params={"n_sims": 2000}).json()
    assert pre["mode"] == "pre-qualifying" and pre["race"]["qualifying_available"] is False
    ingest_loaded_session(db, make_fake_session(seed=7, round_number=3), 2024, "Q")
    post = client.get("/api/v1/predictions/2024/rounds/3", params={"n_sims": 2000}).json()
    assert post["mode"] == "post-qualifying" and post["race"]["qualifying_available"] is True
    grid = {d["driver"]: d["grid"] for d in post["drivers"]}
    assert grid == {"AAA": 1, "BBB": 2, "CCC": 3, "DDD": 4}        # qualifying order from the ingested session
    assert client.get("/api/v1/predictions/2024/rounds/4", params={"n_sims": 2000}).json()["mode"] == "pre-qualifying"
    # the upcoming list reports it too
    upcoming = {u["round"]: u for u in client.get("/api/v1/predictions/2024").json()["upcoming"]}
    assert upcoming[3]["qualifying_available"] is True and upcoming[4]["qualifying_available"] is False
