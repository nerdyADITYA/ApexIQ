from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ml import championship_model

router = APIRouter(prefix="/championships", tags=["championships"])


def _forecast(db, year, n_sims, seed):
    try:
        return championship_model.forecast(db, year, n_sims=n_sims, seed=seed)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.get("/{year}/drivers")
def drivers(year: int, n_sims: int = Query(5000, ge=500, le=50000), seed: int = 0, db: Session = Depends(get_db)):
    f = _forecast(db, year, n_sims, seed)
    return {k: v for k, v in f.items() if k != "constructors"}


@router.get("/{year}/constructors")
def constructors(year: int, n_sims: int = Query(5000, ge=500, le=50000), seed: int = 0, db: Session = Depends(get_db)):
    f = _forecast(db, year, n_sims, seed)
    return {k: v for k, v in f.items() if k != "drivers"}
