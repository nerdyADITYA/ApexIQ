from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import telemetry as tl
from app.core.database import get_db
from app.models import database_models as m

router = APIRouter(tags=["telemetry"])

RAW_COLS = ["time_s", "distance_m", "x", "y", "speed_kph", "throttle", "brake", "gear", "rpm"]


def _load_trace(db: Session, session_id: int, code: str):
    """(lap, cleaned trace) for the driver's stored telemetry lap, or raises 404/422."""
    row = db.execute(
        select(m.Lap).join(m.SessionEntry).join(m.Driver)
        .where(m.SessionEntry.session_id == session_id, m.Driver.code == code.upper())
        .where(m.Lap.id.in_(select(m.TelemetryPoint.lap_id).distinct()))
    ).first()
    if row is None:
        raise HTTPException(404, f"No telemetry stored for {code.upper()} in session {session_id}")
    lap = row[0]
    pts = db.scalars(select(m.TelemetryPoint).where(m.TelemetryPoint.lap_id == lap.id)
                     .order_by(m.TelemetryPoint.sample_index)).all()
    import pandas as pd
    df = pd.DataFrame([{"time_s": None if p.time_ms is None else p.time_ms / 1000.0, "distance_m": p.distance_m,
                        "x": p.x, "y": p.y, "speed_kph": p.speed_kph, "throttle": p.throttle,
                        "brake": p.brake, "gear": p.gear, "rpm": p.rpm} for p in pts], columns=RAW_COLS)
    try:
        trace = tl.clean_trace(df)
    except tl.TelemetryError as exc:
        raise HTTPException(422, str(exc))
    trace, scale = tl.align_to_lap_time(trace, None if lap.lap_time_ms is None else lap.lap_time_ms / 1000.0)
    trace.attrs["time_scale"] = scale
    return lap, trace


def _r(series, nd=2):
    return [None if v != v else round(float(v), nd) for v in series]


def _geometry(lap, trace, n=400):
    """Track payload from one lap; returns (track dict | None, centre_offset | None, markers)."""
    try:
        cl = tl.build_centerline(trace, n=n)
    except tl.TelemetryError:
        return None, None, {"sectors": [], "corners": []}
    off = cl["centre_offset"]
    track = {"x": _r(cl["x"], 1), "y": _r(cl["y"], 1), "length_m": round(cl["length_m"], 1),
             "extent_m": round(cl["extent_m"], 1)}
    markers = {"sectors": tl.sector_markers(trace, off, lap.sector1_ms, lap.sector2_ms),
               "corners": tl.approximate_corners(trace, off)}
    return track, off, markers


@router.get("/telemetry/sessions")
def telemetry_sessions(db: Session = Depends(get_db)):
    """Sessions that have stored lap telemetry, with the drivers available."""
    rows = db.execute(
        select(m.SessionRow, m.Event, m.Season.year, m.Driver.code, m.Lap.lap_number, m.Lap.lap_time_ms)
        .select_from(m.Lap)
        .join(m.SessionEntry, m.Lap.session_entry_id == m.SessionEntry.id)
        .join(m.SessionRow, m.SessionEntry.session_id == m.SessionRow.id)
        .join(m.Event, m.SessionRow.event_id == m.Event.id)
        .join(m.Season, m.Event.season_id == m.Season.id)
        .join(m.Driver, m.SessionEntry.driver_id == m.Driver.id)
        .where(m.Lap.id.in_(select(m.TelemetryPoint.lap_id).distinct()))
        .order_by(m.Season.year.desc(), m.Event.round_number, m.Lap.lap_time_ms)
    ).all()
    out: dict[int, dict] = {}
    for sess, ev, year, code, lap_no, lap_ms in rows:
        s = out.setdefault(sess.id, {"session_id": sess.id, "year": year, "round": ev.round_number,
                                     "event": ev.event_name, "type": sess.session_type, "circuit_id": ev.circuit_id,
                                     "drivers": []})
        s["drivers"].append({"code": code, "lap_number": lap_no,
                             "lap_time_s": None if lap_ms is None else lap_ms / 1000.0})
    return list(out.values())


@router.get("/sessions/{session_id}/lap-comparison")
def lap_comparison(session_id: int, a: str, b: str | None = None, points: int = Query(300, ge=50, le=800),
                   db: Session = Depends(get_db)):
    """Aligned-by-distance telemetry for driver A (and optionally B), plus track geometry.

    delta_s = t_B - t_A at each distance: positive means B is behind A."""
    if db.get(m.SessionRow, session_id) is None:
        raise HTTPException(404, "Session not found")
    lap_a, ta = _load_trace(db, session_id, a)
    track, off, markers = _geometry(lap_a, ta)

    def pack(res):
        return {c: _r(res[c], 3 if c in ("time_s", "x", "y") else 1) for c in
                ["time_s", "speed_kph", "throttle", "brake", "gear", "rpm", "x", "y"]}

    notes = ["Geometry is reconstructed from one lap's position samples: approximate, flat, not surveyed.",
             "Corner markers (A1, A2, ...) are speed-trace minima, not official corner numbers.",
             "Positions are telemetry replay, not a physics simulation."]
    if track is None:
        notes.append("No position data for this lap: the 3D track cannot be drawn.")
    notes.append("Each lap's time axis is scaled so its duration equals the official lap time (stored traces can "
                 "differ by a few tenths), so the final delta equals the official lap-time difference.")

    if b is None:
        r = tl.resample_by_distance(ta, points)
        samples = {"distance_m": _r(r["distance_m"], 1), "a": pack(r)}
        delta, length = None, float(ta["distance_m"].iloc[-1])
        lap_b = None
    else:
        lap_b, tb = _load_trace(db, session_id, b)
        cmp_ = tl.delta_time(ta, tb, points)
        samples = {"distance_m": _r(cmp_["distance_m"], 1), "a": pack(cmp_["a"]), "b": pack(cmp_["b"]),
                   "delta_s": _r(cmp_["delta_s"], 3)}
        length = cmp_["compared_length_m"]

    def lap_info(code, lap):
        return {"code": code.upper(), "lap_number": lap.lap_number,
                "lap_time_s": None if lap.lap_time_ms is None else lap.lap_time_ms / 1000.0}

    # Express B's x/y in A's scene frame (same centre offset)
    if b is not None and off is not None:
        for k in ("x", "y"):
            idx = 0 if k == "x" else 1
            samples["b"][k] = _r([v * tl.XY_TO_M - off[idx] if v is not None and v == v else float("nan")
                                  for v in samples["b"][k]], 3)
    if off is not None:
        for k in ("x", "y"):
            idx = 0 if k == "x" else 1
            samples["a"][k] = _r([v * tl.XY_TO_M - off[idx] if v is not None and v == v else float("nan")
                                  for v in samples["a"][k]], 3)

    return {"session_id": session_id, "a": lap_info(a, lap_a), "b": None if lap_b is None else lap_info(b, lap_b),
            "has_position": track is not None, "track": track, "markers": markers,
            "compared_length_m": round(length, 1), "samples": samples, "notes": notes}


@router.get("/circuits/{circuit_id}/geometry")
def circuit_geometry(circuit_id: int, db: Session = Depends(get_db)):
    """Approximate centreline from the quickest stored telemetry lap at this circuit."""
    circuit = db.get(m.Circuit, circuit_id)
    if circuit is None:
        raise HTTPException(404, "Circuit not found")
    row = db.execute(
        select(m.Lap, m.SessionEntry.session_id).join(m.SessionEntry).join(m.SessionRow).join(m.Event)
        .where(m.Event.circuit_id == circuit_id, m.Lap.lap_time_ms.is_not(None))
        .where(m.Lap.id.in_(select(m.TelemetryPoint.lap_id).where(m.TelemetryPoint.x.is_not(None)).distinct()))
        .order_by(m.Lap.lap_time_ms).limit(1)
    ).first()
    if row is None:
        raise HTTPException(404, "No telemetry stored for this circuit")
    lap, session_id = row
    code = db.scalar(select(m.Driver.code).join(m.SessionEntry).where(m.SessionEntry.id == lap.session_entry_id))
    _, trace = _load_trace(db, session_id, code)
    track, _, markers = _geometry(lap, trace)
    if track is None:
        raise HTTPException(422, "Stored telemetry has no position data")
    return {"circuit": circuit.name, "country": circuit.country, "reference": {"session_id": session_id, "driver": code},
            "track": track, "markers": markers,
            "notes": ["Approximate, flat reconstruction from telemetry; not surveyed geometry."]}
