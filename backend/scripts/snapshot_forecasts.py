"""Usage: python -m scripts.snapshot_forecasts 2026

Saves a snapshot of the current forecast for every upcoming race. Safe to run repeatedly: a snapshot is replaced by a
newer one of the same mode until its race has been run, and is frozen for good afterwards."""
import sys

sys.path.insert(0, ".")

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import database_models  # noqa: F401,E402
from app.services import forecast_service as fs  # noqa: E402

if __name__ == "__main__":
    year = int(sys.argv[1])
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for row in fs.snapshot_upcoming(db, year):
            detail = row.get("model_version") or row.get("reason")
            print(f"round {row['round']:>2} {row['event']:<28} {row['status']}: {row.get('mode', '')} {detail}")
