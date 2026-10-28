"""Usage: python -m scripts.merge_circuit_aliases   (idempotent)

Re-points events at the canonical circuit for every known alias and removes the orphaned alias rows."""
import sys

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.data.ingestion import CIRCUIT_ALIASES  # noqa: E402
from app.models import database_models as m  # noqa: E402


def merge(db) -> dict[str, int]:
    moved = {}
    for alias, canon in CIRCUIT_ALIASES.items():
        old = db.scalar(select(m.Circuit).where(m.Circuit.name == alias))
        if old is None:
            continue
        target = db.scalar(select(m.Circuit).where(m.Circuit.name == canon))
        if target is None:                       # canonical row absent: simply rename the alias row
            old.name = canon
            moved[alias] = 0
            continue
        events = db.scalars(select(m.Event).where(m.Event.circuit_id == old.id)).all()
        for e in events:
            e.circuit_id = target.id
        for field in ("country", "latitude", "longitude", "track_length_m"):
            if getattr(target, field) is None and getattr(old, field) is not None:
                setattr(target, field, getattr(old, field))
        db.flush()
        db.delete(old)
        moved[alias] = len(events)
    db.commit()
    return moved


if __name__ == "__main__":
    with SessionLocal() as db:
        print("merged:", merge(db) or "nothing to do")
