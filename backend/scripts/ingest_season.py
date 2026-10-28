"""Usage: python scripts/ingest_season.py 2024 [--telemetry] [--sessions R,Q] [--rounds 1,8,12] [--new-only] [--no-snapshot]

Ingests every round of a season. Failures are reported and skipped so one bad
round does not stop the run; re-running is safe (ingestion is idempotent).
"""
import sys
import warnings

import pandas as pd

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.data import fastf1_loader  # noqa: E402
from app.data.ingestion import ingest_session, upsert_schedule  # noqa: E402
from app.models import database_models  # noqa: F401,E402
from app.models import database_models as m  # noqa: E402
from sqlalchemy import select  # noqa: E402

NAME_TO_CODE = {
    "Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3", "Qualifying": "Q",
    "Sprint Qualifying": "SQ", "Sprint Shootout": "SS", "Sprint": "S", "Race": "R",
}

if __name__ == "__main__":
    import logging

    configure_logging(logging.ERROR)
    year = int(sys.argv[1])
    telemetry = "--telemetry" in sys.argv
    new_only = "--new-only" in sys.argv   # skip sessions already stored: cheap refresh of a running season
    types = ["R"]
    if "--sessions" in sys.argv:
        types = sys.argv[sys.argv.index("--sessions") + 1].split(",")

    only_rounds = None
    if "--rounds" in sys.argv:
        only_rounds = {int(r) for r in sys.argv[sys.argv.index("--rounds") + 1].split(",")}

    now = pd.Timestamp.utcnow().tz_localize(None)
    Base.metadata.create_all(engine)
    failures = []
    ingested = 0
    with SessionLocal() as db:
        schedule = fastf1_loader.get_schedule(year)
        upsert_schedule(db, year, schedule)
        already_loaded = set()
        if new_only:
            already_loaded = {
                (year, e.round_number, s.session_type)
                for s, e in db.execute(
                    select(m.SessionRow, m.Event).join(m.Event).join(m.Season)
                    .where(m.Season.year == year, m.SessionRow.status == "loaded"))}
        for _, row in schedule.iterrows():
            rnd = int(row["RoundNumber"])
            if only_rounds is not None and rnd not in only_rounds:
                continue
            # Only sessions that have already happened (UTC); lets an in-progress season be re-run safely
            held = set()
            for i in range(1, 6):
                code = NAME_TO_CODE.get(row.get(f"Session{i}"))
                when = row.get(f"Session{i}DateUtc")
                if code and (pd.isna(when) or pd.Timestamp(when) <= now):
                    held.add(code)
            for st in (t for t in types if t in held):
                if new_only and (year, rnd, st) in already_loaded:
                    continue
                try:
                    s = ingest_session(db, year, rnd, st, include_telemetry=telemetry)
                    ingested += 1
                    print(f"round {rnd:>2} {row['EventName']:<32} {st}: {s['laps']} laps, {s['pit_stops']} stops", flush=True)
                except Exception as exc:
                    db.rollback()
                    failures.append((rnd, st, str(exc)[:120]))
                    print(f"round {rnd:>2} {row['EventName']:<32} {st}: FAILED {exc!s:.100}", flush=True)
        # New results change the forecasts of upcoming races: save fresh snapshots (frozen once each race is run)
        if ingested and "--no-snapshot" not in sys.argv:
            from app.services import forecast_service as fs
            for r in fs.snapshot_upcoming(db, year):
                print(f"snapshot round {r['round']:>2} {r['event']:<28} {r['status']} {r.get('mode', r.get('reason', ''))}", flush=True)
    print(f"\nDone. {len(failures)} failure(s).")
