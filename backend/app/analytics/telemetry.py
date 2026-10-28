"""Telemetry cleaning, lap comparison and circuit geometry (pure functions, no DB).

Units: distance in metres, time in seconds, speed in km/h. FastF1 X/Y are in 1/10 m
and are converted to metres here. Geometry is reconstructed from one lap's GPS-like
position samples: it is approximate, flat (no elevation) and NOT surveyed geometry.
"""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

XY_TO_M = 0.1
CHANNELS = ["time_s", "speed_kph", "throttle", "brake", "gear", "rpm", "x", "y"]


class TelemetryError(Exception):
    pass


def clean_trace(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by sample order, drop rows without time/distance, and make time and distance
    non-decreasing, dropping repeated distance samples so interpolation is well defined."""
    t = df.dropna(subset=["time_s", "distance_m"]).sort_values("time_s").copy()
    t["distance_m"] = np.maximum.accumulate(t["distance_m"].to_numpy())
    t = t.drop_duplicates(subset="distance_m", keep="first")
    if len(t) < 20:
        raise TelemetryError("Too few valid telemetry samples")
    t["time_s"] = t["time_s"] - t["time_s"].iloc[0]
    return t.reset_index(drop=True)


def align_to_lap_time(t: pd.DataFrame, lap_time_s: float | None, tol: float = 0.015) -> tuple[pd.DataFrame, float | None]:
    """Scale the time axis so the trace lasts exactly the official lap time.

    Stored traces can end a few tenths early or late relative to the timed lap, which is larger
    than many real gaps between drivers. Uniform scaling (assumes the error is spread evenly)
    makes the final delta between two laps equal the official lap-time difference. Returns
    (trace, scale); scale is None when no official time exists or the mismatch exceeds `tol`
    (a mismatch that large is not timing jitter, so the trace is left untouched)."""
    if not lap_time_s:
        return t, None
    duration = float(t["time_s"].iloc[-1])
    if duration <= 0 or abs(duration - lap_time_s) / lap_time_s > tol:
        return t, None
    out = t.copy()
    scale = lap_time_s / duration
    out["time_s"] = out["time_s"] * scale
    return out, scale


def has_position(t: pd.DataFrame) -> bool:
    return bool(t["x"].notna().mean() > 0.9 and t["y"].notna().mean() > 0.9)


def resample_by_distance(t: pd.DataFrame, n: int = 300, length: float | None = None) -> pd.DataFrame:
    """Resample every channel onto n evenly spaced distances in [0, length]."""
    d = t["distance_m"].to_numpy()
    length = float(length if length is not None else d[-1])
    grid = np.linspace(0.0, length, n)
    out = {"distance_m": grid}
    for c in CHANNELS:
        if c not in t or t[c].notna().sum() < 2:
            out[c] = np.full(n, np.nan)
            continue
        ok = t[c].notna().to_numpy()
        vals = np.interp(grid, d[ok], t[c].to_numpy()[ok])
        out[c] = np.round(vals) if c == "gear" else vals
    return pd.DataFrame(out)


def delta_time(a: pd.DataFrame, b: pd.DataFrame, n: int = 300) -> dict:
    """Time gap of B relative to A along the lap: delta(d) = t_B(d) - t_A(d).
    Positive means B is behind A at that distance.

    Each car's distance is integrated from its own speed trace, so the two totals differ by
    a few metres (about 0.1 to 0.3%) even though both cover the same physical lap. Comparing
    at raw distance would cut one lap short of its end, so each trace's distance is rescaled to
    the mean of the two totals; the final delta is then the full-lap time difference."""
    da, db = float(a["distance_m"].iloc[-1]), float(b["distance_m"].iloc[-1])
    length = (da + db) / 2
    a2, b2 = a.copy(), b.copy()
    a2["distance_m"] = a2["distance_m"] * (length / da)
    b2["distance_m"] = b2["distance_m"] * (length / db)
    ra, rb = resample_by_distance(a2, n, length), resample_by_distance(b2, n, length)
    return {"distance_m": ra["distance_m"], "a": ra, "b": rb, "delta_s": rb["time_s"] - ra["time_s"],
            "compared_length_m": float(length), "distance_mismatch_m": abs(da - db)}


def _smooth_closed(v: np.ndarray, window: int) -> np.ndarray:
    k = np.ones(window) / window
    pad = window // 2
    ext = np.concatenate([v[-pad:], v, v[:pad]])
    return np.convolve(ext, k, mode="same")[pad:-pad]


def build_centerline(t: pd.DataFrame, n: int = 400, smooth_window: int = 5) -> dict:
    """Uniform-arc-length, smoothed, closed centreline in metres, centred on its midpoint.

    Raises TelemetryError when position data is missing. Returned `s` is the cumulative
    arc length of each point along the reconstructed line (m)."""
    if not has_position(t):
        raise TelemetryError("No position (x, y) data for this lap")
    p = t.dropna(subset=["x", "y"])
    x, y = p["x"].to_numpy() * XY_TO_M, p["y"].to_numpy() * XY_TO_M
    # Close the loop: a lap starts and ends at the line, so append the first point if the gap is large.
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] <= 0:
        raise TelemetryError("Degenerate position data")
    grid = np.linspace(0, s[-1], n, endpoint=False)
    gx, gy = np.interp(grid, s, x), np.interp(grid, s, y)
    gx, gy = _smooth_closed(gx, smooth_window), _smooth_closed(gy, smooth_window)
    cx, cy = (gx.max() + gx.min()) / 2, (gy.max() + gy.min()) / 2
    gx, gy = gx - cx, gy - cy
    closed_len = float(np.sum(np.hypot(np.diff(np.append(gx, gx[0])), np.diff(np.append(gy, gy[0])))))
    return {"x": gx, "y": gy, "length_m": closed_len, "centre_offset": (float(cx), float(cy)),
            "extent_m": float(max(np.ptp(gx), np.ptp(gy)))}


def to_scene(t: pd.DataFrame, centre_offset: tuple[float, float]) -> pd.DataFrame:
    """Express a trace's x/y in the same metre frame as the centerline."""
    out = t.copy()
    out["x"] = out["x"] * XY_TO_M - centre_offset[0]
    out["y"] = out["y"] * XY_TO_M - centre_offset[1]
    return out


def position_at_distance(t: pd.DataFrame, centre_offset, distance_m: float) -> tuple[float, float]:
    d = t["distance_m"].to_numpy()
    return (float(np.interp(distance_m, d, t["x"].to_numpy()) * XY_TO_M - centre_offset[0]),
            float(np.interp(distance_m, d, t["y"].to_numpy()) * XY_TO_M - centre_offset[1]))


def sector_markers(t: pd.DataFrame, centre_offset, s1_ms, s2_ms) -> list[dict]:
    """Sector 1/2 ends located by lap time along the trace (needs sector times); None if unavailable."""
    out = []
    if s1_ms is None:
        return out
    time_s, dist = t["time_s"].to_numpy(), t["distance_m"].to_numpy()
    for label, secs in (("S1 end", s1_ms / 1000.0), ("S2 end", (s1_ms + s2_ms) / 1000.0 if s2_ms is not None else None)):
        if secs is None or secs >= time_s[-1]:
            continue
        d = float(np.interp(secs, time_s, dist))
        x, y = position_at_distance(t, centre_offset, d)
        out.append({"label": label, "distance_m": d, "x": x, "y": y})
    return out


def approximate_corners(t: pd.DataFrame, centre_offset, min_prominence_kph: float = 25.0,
                        min_separation_m: float = 120.0) -> list[dict]:
    """Local speed minima along the lap, numbered in order. These are speed-trace apexes,
    NOT official corner numbers."""
    r = resample_by_distance(t, n=800)
    step = float(r["distance_m"].iloc[1] - r["distance_m"].iloc[0])
    peaks, props = find_peaks(-r["speed_kph"].to_numpy(), prominence=min_prominence_kph,
                              distance=max(int(min_separation_m / step), 1))
    out = []
    for i, k in enumerate(peaks, 1):
        d = float(r["distance_m"].iloc[k])
        x, y = position_at_distance(t, centre_offset, d)
        out.append({"label": f"A{i}", "distance_m": d, "min_speed_kph": float(r["speed_kph"].iloc[k]), "x": x, "y": y})
    return out
