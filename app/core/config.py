from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationError(RuntimeError):
    """Raised when the application configuration is unsafe or incomplete."""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "Data Reliability Copilot"
    app_version: str = "1.2.0"
    service_name: str = "data-reliability-copilot"
    environment: str = Field(default_factory=lambda: os.getenv("DRC_ENVIRONMENT", "development").strip().lower())
    session_cookie_name: str = Field(default_factory=lambda: os.getenv("DRC_SESSION_COOKIE", "drc_session"))
    session_hours: int = Field(default_factory=lambda: int(os.getenv("DRC_SESSION_HOURS", "12")))
    secure_cookies: bool = Field(default_factory=lambda: os.getenv("DRC_SECURE_COOKIES", "false").lower() == "true")
    bootstrap_admin_email: str = Field(default_factory=lambda: os.getenv("DRC_ADMIN_EMAIL", "admin@example.invalid"))
    bootstrap_admin_password: str = Field(default_factory=lambda: os.getenv("DRC_ADMIN_PASSWORD", "replace-with-a-strong-random-password"))
    bootstrap_admin_name: str = Field(default_factory=lambda: os.getenv("DRC_ADMIN_NAME", "DRC Administrator"))
    storage_backend: str = Field(default_factory=lambda: os.getenv("DRC_STORAGE_BACKEND", "local").strip().lower())
    gcs_bucket: str | None = Field(default_factory=lambda: os.getenv("DRC_GCS_BUCKET") or None)
    run_migrations: bool = Field(default_factory=lambda: os.getenv("DRC_RUN_MIGRATIONS", "true").lower() == "true")
    enable_internal_scheduler: bool = Field(default_factory=lambda: os.getenv("DRC_ENABLE_INTERNAL_SCHEDULER", "true").lower() == "true")
    max_upload_bytes: int = Field(default_factory=lambda: int(os.getenv("DRC_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))))
    root_dir: Path = Path(__file__).resolve().parents[2]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def static_dir(self) -> Path:
        return self.root_dir / "app" / "static"

    @property
    def sample_dataset(self) -> Path:
        return self.root_dir / "samples" / "customers_dirty.csv"

    @property
    def data_dir(self) -> Path:
        configured = os.getenv("DRC_STORAGE_ROOT")
        return Path(configured).expanduser().resolve() if configured else self.root_dir / "data"

    @property
    def audit_dir(self) -> Path:
        return self.data_dir / "audits"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def report_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    @property
    def database_path(self) -> Path:
        configured = os.getenv("DRC_DATABASE_PATH")
        return Path(configured).expanduser().resolve() if configured else self.data_dir / "drc.db"

    @property
    def database_url(self) -> str:
        configured = os.getenv("DRC_DATABASE_URL")
        return configured or f"sqlite:///{self.database_path.as_posix()}"

    def validate_runtime_configuration(self) -> None:
        errors: list[str] = []
        if self.environment not in {"development", "testing", "staging", "production"}:
            errors.append("DRC_ENVIRONMENT must be development, testing, staging, or production.")
        if self.session_hours < 1:
            errors.append("DRC_SESSION_HOURS must be at least 1.")
        if self.max_upload_bytes < 1:
            errors.append("DRC_MAX_UPLOAD_BYTES must be greater than zero.")
        if self.storage_backend not in {"local", "gcs"}:
            errors.append("DRC_STORAGE_BACKEND must be 'local' or 'gcs'.")
        if self.storage_backend == "gcs" and not self.gcs_bucket:
            errors.append("DRC_GCS_BUCKET is required when DRC_STORAGE_BACKEND=gcs.")
        if self.is_production:
            if self.database_url.startswith("sqlite"):
                errors.append("Production requires PostgreSQL; SQLite is not permitted.")
            if not self.secure_cookies:
                errors.append("DRC_SECURE_COOKIES must be true in production.")
            if self.enable_internal_scheduler:
                errors.append("Disable the internal scheduler in production and use a dedicated scheduler service.")
            if self.bootstrap_admin_email in {"admin@drc.local", "admin@example.invalid"}:
                errors.append("Set a unique DRC_ADMIN_EMAIL in production.")
            if self.bootstrap_admin_password in {"ChangeMe123!", "replace-with-a-strong-random-password"} or len(self.bootstrap_admin_password) < 16:
                errors.append("Set a unique DRC_ADMIN_PASSWORD of at least 16 characters in production.")
        if errors:
            raise ConfigurationError("Invalid DRC configuration:\n- " + "\n- ".join(errors))

    def ensure_runtime_directories(self) -> None:
        if self.storage_backend == "local":
            for directory in (self.audit_dir, self.upload_dir, self.report_dir, self.temp_dir):
                directory.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite"):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime_configuration()
    settings.ensure_runtime_directories()
    return settings
