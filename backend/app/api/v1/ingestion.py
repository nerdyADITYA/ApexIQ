from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.data import ingestion as ing
from app.models import database_models as m
from app.models.schemas import IngestionJob, IngestionRequest

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _run(job_id: int, req: IngestionRequest):
    # Own DB session: the request-scoped one is closed once the response is sent.
    db = SessionLocal()
    job = db.get(m.IngestionRun, job_id)
    try:
        summary = ing.ingest_session(db, req.year, req.event, req.session_type, req.include_telemetry)
        job = db.get(m.IngestionRun, job_id)
        job.status = "success"
        job.records_processed = summary["laps"] + summary["pit_stops"] + summary["telemetry_points"]
    except Exception as exc:
        db.rollback()
        job = db.get(m.IngestionRun, job_id)
        job.status = "failed"
        job.error_message = str(exc)[:500]
    finally:
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.close()


@router.post("/jobs", response_model=IngestionJob, status_code=202)
def start(req: IngestionRequest, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Runs in-process via BackgroundTasks for now; swap for RQ/Celery when scaling out."""
    job = m.IngestionRun(status="queued", request=req.model_dump())
    db.add(job)
    db.commit()
    tasks.add_task(_run, job.id, req)
    return IngestionJob(job_id=job.id, status=job.status, started_at=job.started_at)


@router.get("/jobs/{job_id}", response_model=IngestionJob)
def status(job_id: int, db: Session = Depends(get_db)):
    job = db.get(m.IngestionRun, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return IngestionJob(job_id=job.id, status=job.status, started_at=job.started_at,
                        completed_at=job.completed_at, error_message=job.error_message,
                        records_processed=job.records_processed)
