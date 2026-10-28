import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analytics import telemetry as tl
from app.core.database import get_db
from app.data.ingestion import ingest_loaded_session
from app.main import app
from tests.conftest import make_fake_session

R = 500.0  # metres


def circle_trace(lap_time=80.0, n=400, dips=(0.25, 0.75), with_xy=True, speed_scale=1.0):
    """A circular lap of radius R (x/y in 1/10 m like FastF1) with two speed dips."""
    theta = np.linspace(0, 2 * np.pi, n)
    dist = R * theta
    speed = 250 - 150 * sum(np.exp(-((theta / (2 * np.pi) - c) ** 2) / 0.0008) for c in dips)
    speed = speed * speed_scale
    ds = np.diff(dist, prepend=dist[0])
    time = np.cumsum(ds / (speed / 3.6))
    time = time / time[-1] * lap_time
    return pd.DataFrame({
        "time_s": time, "distance_m": dist,
        "x": R * np.cos(theta) * 10 if with_xy else np.nan, "y": R * np.sin(theta) * 10 if with_xy else np.nan,
        "speed_kph": speed, "throttle": 100.0, "brake": 0.0, "gear": 6, "rpm": 10000.0})


def test_clean_trace_makes_distance_monotonic_and_rejects_short():
    df = circle_trace()
    df.loc[50, "distance_m"] = 0.0   # glitch backwards
    t = tl.clean_trace(df)
    assert (np.diff(t["distance_m"]) > 0).all() and t["time_s"].iloc[0] == 0
    with pytest.raises(tl.TelemetryError):
        tl.clean_trace(df.head(5))


def test_centerline_is_closed_centred_and_right_length():
    cl = tl.build_centerline(tl.clean_trace(circle_trace()))
    assert abs(cl["length_m"] - 2 * np.pi * R) / (2 * np.pi * R) < 0.02
    assert abs(cl["x"].mean()) < 5 and abs(cl["y"].mean()) < 5
    assert abs(cl["extent_m"] - 2 * R) < 0.03 * 2 * R
    # closed: the wrap-around step is the same size as any other step
    steps = np.hypot(np.diff(np.append(cl["x"], cl["x"][0])), np.diff(np.append(cl["y"], cl["y"][0])))
    assert steps.max() / steps.min() < 1.3


def test_centerline_without_position_raises():
    with pytest.raises(tl.TelemetryError):
        tl.build_centerline(tl.clean_trace(circle_trace(with_xy=False)))


def test_delta_time_sign_and_total():
    fast = tl.clean_trace(circle_trace(lap_time=80.0))
    slow = tl.clean_trace(circle_trace(lap_time=81.0))
    d = tl.delta_time(fast, slow)
    delta = d["delta_s"].to_numpy()
    assert delta[0] == 0 and abs(delta[-1] - 1.0) < 0.02       # B (slow) finishes 1.0 s behind A
    assert (np.diff(delta) > -1e-6).all()                       # gap only grows for a uniformly slower lap
    flipped = tl.delta_time(slow, fast)["delta_s"].to_numpy()
    assert abs(flipped[-1] + 1.0) < 0.02


def test_approximate_corners_find_speed_dips():
    t = tl.clean_trace(circle_trace())
    corners = tl.approximate_corners(t, (0.0, 0.0))
    assert len(corners) == 2
    quarter, three_quarter = 0.25 * 2 * np.pi * R, 0.75 * 2 * np.pi * R
    assert abs(corners[0]["distance_m"] - quarter) < 60 and abs(corners[1]["distance_m"] - three_quarter) < 60
    assert all(c["min_speed_kph"] < 130 for c in corners)


def test_sector_markers_by_time():
    t = tl.clean_trace(circle_trace(lap_time=80.0))
    m = tl.sector_markers(t, (0.0, 0.0), 25_000, 30_000)
    assert [x["label"] for x in m] == ["S1 end", "S2 end"] and m[0]["distance_m"] < m[1]["distance_m"]
    assert tl.sector_markers(t, (0.0, 0.0), None, None) == []


def _telemetry_for(df):
    return pd.DataFrame({"Time": pd.to_timedelta(df["time_s"], unit="s"), "Distance": df["distance_m"],
                         "X": df["x"], "Y": df["y"], "Speed": df["speed_kph"], "Throttle": df["throttle"],
                         "Brake": df["brake"] > 0, "nGear": df["gear"], "RPM": df["rpm"]})


@pytest.fixture
def client(db):
    tel = {"AAA": (20, _telemetry_for(circle_trace(80.0))), "BBB": (20, _telemetry_for(circle_trace(81.0))),
           "CCC": (20, _telemetry_for(circle_trace(82.0, with_xy=False)))}
    ingest_loaded_session(db, make_fake_session(), 2024, "R", telemetry=tel)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_telemetry_sessions_listing(client):
    r = client.get("/api/v1/telemetry/sessions").json()
    assert len(r) == 1 and {d["code"] for d in r[0]["drivers"]} == {"AAA", "BBB", "CCC"}


def test_lap_comparison_endpoint(client):
    r = client.get("/api/v1/sessions/1/lap-comparison", params={"a": "AAA", "b": "BBB", "points": 120}).json()
    assert r["has_position"] and len(r["track"]["x"]) == 400
    s = r["samples"]
    assert len(s["distance_m"]) == len(s["delta_s"]) == len(s["a"]["speed_kph"]) == 120
    assert abs(s["delta_s"][-1] - 1.0) < 0.05 and s["delta_s"][0] == 0
    assert abs(r["track"]["length_m"] - 2 * np.pi * R) < 0.03 * 2 * np.pi * R
    assert len(r["markers"]["corners"]) == 2
    # both drivers share the same scene frame: positions stay within the track extent
    ax = max(abs(v) for v in s["a"]["x"] if v is not None)
    assert ax < r["track"]["extent_m"]


def test_single_driver_and_errors(client):
    r = client.get("/api/v1/sessions/1/lap-comparison", params={"a": "AAA"}).json()
    assert r["b"] is None and "delta_s" not in r["samples"]
    assert client.get("/api/v1/sessions/1/lap-comparison", params={"a": "ZZZ"}).status_code == 404
    assert client.get("/api/v1/sessions/999/lap-comparison", params={"a": "AAA"}).status_code == 404
    assert client.get("/api/v1/sessions/1/lap-comparison", params={"a": "AAA", "points": 5}).status_code == 422


def test_missing_position_gives_fallback_not_error(client):
    r = client.get("/api/v1/sessions/1/lap-comparison", params={"a": "CCC"}).json()
    assert r["has_position"] is False and r["track"] is None
    assert any("cannot be drawn" in n for n in r["notes"])
    assert len(r["samples"]["a"]["speed_kph"]) == 300   # charts still work


def test_circuit_geometry_endpoint(client):
    g = client.get("/api/v1/circuits/1/geometry").json()
    # CCC has no position data, so it can never be the reference even if its lap time is quickest
    assert g["reference"]["driver"] in ("AAA", "BBB")
    assert abs(g["track"]["length_m"] - 2 * np.pi * R) < 0.03 * 2 * np.pi * R
    assert client.get("/api/v1/circuits/999/geometry").status_code == 404


def test_align_to_lap_time_scales_duration_and_respects_tolerance():
    t = tl.clean_trace(circle_trace(lap_time=79.7))
    aligned, scale = tl.align_to_lap_time(t, 80.0)
    assert abs(aligned["time_s"].iloc[-1] - 80.0) < 1e-9 and abs(scale - 80.0 / 79.7) < 1e-9
    same, none = tl.align_to_lap_time(t, 90.0)            # 12% off: not jitter, leave untouched
    assert none is None and same["time_s"].iloc[-1] == t["time_s"].iloc[-1]
    assert tl.align_to_lap_time(t, None)[1] is None


def test_final_delta_equals_official_lap_time_difference():
    # traces whose raw durations are 0.3 s off their official times must still give the official gap
    a = tl.align_to_lap_time(tl.clean_trace(circle_trace(lap_time=79.7)), 80.000)[0]
    b = tl.align_to_lap_time(tl.clean_trace(circle_trace(lap_time=80.6)), 80.200)[0]
    assert abs(tl.delta_time(a, b)["delta_s"].iloc[-1] - 0.200) < 0.01


def test_delta_survives_different_integrated_distances():
    # same lap, but car B's integrated distance is 0.3% shorter: the gap must still be the full time difference
    a = tl.clean_trace(circle_trace(lap_time=80.0))
    b_raw = circle_trace(lap_time=80.2)
    b_raw["distance_m"] = b_raw["distance_m"] * 0.997
    d = tl.delta_time(a, tl.clean_trace(b_raw))
    assert abs(d["delta_s"].iloc[-1] - 0.2) < 0.01
    assert d["distance_mismatch_m"] > 5
