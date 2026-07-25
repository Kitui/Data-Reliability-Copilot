from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    alerts,
    audits,
    auth,
    connectors,
    copilot,
    datasets,
    jobs,
    quality_rules,
    reports,
    schedules,
    schema_drift,
    security,
    system,
    team,
    workspaces,
)
from app.auth import ensure_bootstrap_admin
from app.core.config import get_settings
from app.core.errors import unhandled_exception_handler
from app.core.observability import ObservabilityMiddleware, configure_logging
from app.core.security_middleware import SecurityMiddleware
from app.db.migrations import run_migrations
from app.tenancy import ensure_bootstrap_tenant


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.run_migrations:
        run_migrations()
    ensure_bootstrap_admin()
    ensure_bootstrap_tenant()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Audit, explain, govern, and improve data reliability.",
        lifespan=lifespan,
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        )
    application.add_middleware(SecurityMiddleware)
    application.add_middleware(ObservabilityMiddleware)
    application.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    application.include_router(system.router)
    application.include_router(security.router)
    application.include_router(auth.router)
    application.include_router(workspaces.router)
    application.include_router(team.router)
    application.include_router(datasets.router)
    application.include_router(jobs.router)
    application.include_router(schema_drift.router)
    application.include_router(schedules.router)
    application.include_router(alerts.router)
    application.include_router(connectors.router)
    application.include_router(copilot.router)
    application.include_router(reports.router)
    application.include_router(quality_rules.router)
    application.include_router(audits.router)
    application.add_exception_handler(Exception, unhandled_exception_handler)

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        return (settings.static_dir / "index.html").read_text(encoding="utf-8")

    return application


app = create_app()

# Compatibility exports retained for existing integrations and tests.
load_audit = audits.load_audit
parse_rule_config = audits.parse_rule_config
save_upload = audits.save_upload
