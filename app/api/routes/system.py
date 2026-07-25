from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["System"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    database_status = "ok"
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "service": settings.service_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": database_status,
    }
