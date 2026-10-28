"""Usage: python scripts/ingest_session.py 2024 Monaco R [--no-telemetry]"""
import sys

sys.path.insert(0, ".")

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.data.ingestion import ingest_session, upsert_schedule  # noqa: E402
from app.data import fastf1_loader  # noqa: E402
from app.models import database_models  # noqa: F401,E402

if __name__ == "__main__":
    configure_logging()
    year, event, stype = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if "--schedule" in sys.argv:
            print("schedule rows:", upsert_schedule(db, year, fastf1_loader.get_schedule(year)))
        print(ingest_session(db, year, event, stype, include_telemetry="--no-telemetry" not in sys.argv))
