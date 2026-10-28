from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analytics, championships, ingestion, predictions, seasons, sessions, strategies, telemetry
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.models import database_models  # noqa: F401  (register tables)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Dev convenience only; production should run `alembic upgrade head`.
    if settings.app_env == "development":
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title="F1 Performance Intelligence", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST"], allow_headers=["*"],
)

for r in (seasons.router, sessions.router, analytics.router, telemetry.router, predictions.router, championships.router, strategies.router, ingestion.router):
    app.include_router(r, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}
