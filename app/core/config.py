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
    app_version: str = "1.6.0"
    service_name: str = "data-reliability-copilot"
    environment: str = Field(default_factory=lambda: os.getenv("DRC_ENVIRONMENT", "development").strip().lower())
    session_cookie_name: str = Field(default_factory=lambda: os.getenv("DRC_SESSION_COOKIE", "drc_session"))
    session_hours: int = Field(default_factory=lambda: int(os.getenv("DRC_SESSION_HOURS", "12")))
    secure_cookies: bool = Field(default_factory=lambda: os.getenv("DRC_SECURE_COOKIES", "false").lower() == "true")
    bootstrap_admin_email: str = Field(default_factory=lambda: os.getenv("DRC_ADMIN_EMAIL", "admin@example.invalid"))
    bootstrap_admin_password: str = Field(
        default_factory=lambda: os.getenv("DRC_ADMIN_PASSWORD", "replace-with-a-strong-random-password")
    )
    bootstrap_admin_name: str = Field(default_factory=lambda: os.getenv("DRC_ADMIN_NAME", "DRC Administrator"))
    storage_backend: str = Field(default_factory=lambda: os.getenv("DRC_STORAGE_BACKEND", "local").strip().lower())
    gcs_bucket: str | None = Field(default_factory=lambda: os.getenv("DRC_GCS_BUCKET") or None)
    run_migrations: bool = Field(default_factory=lambda: os.getenv("DRC_RUN_MIGRATIONS", "true").lower() == "true")
    enable_internal_scheduler: bool = Field(
        default_factory=lambda: os.getenv("DRC_ENABLE_INTERNAL_SCHEDULER", "false").lower() == "true"
    )
    scheduler_token: str | None = Field(default_factory=lambda: os.getenv("DRC_SCHEDULER_TOKEN") or None)
    max_upload_bytes: int = Field(default_factory=lambda: int(os.getenv("DRC_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))))
    allowed_hosts: list[str] = Field(
        default_factory=lambda: [
            x.strip() for x in os.getenv("DRC_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if x.strip()
        ]
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [x.strip() for x in os.getenv("DRC_CORS_ORIGINS", "").split(",") if x.strip()]
    )
    csrf_cookie_name: str = Field(default_factory=lambda: os.getenv("DRC_CSRF_COOKIE", "drc_csrf"))
    csrf_enabled: bool = Field(
        default_factory=lambda: os.getenv(
            "DRC_CSRF_ENABLED",
            "false" if os.getenv("DRC_ENVIRONMENT", "development").strip().lower() == "testing" else "true",
        ).lower()
        == "true"
    )
    login_window_minutes: int = Field(default_factory=lambda: int(os.getenv("DRC_LOGIN_WINDOW_MINUTES", "15")))
    login_max_attempts: int = Field(default_factory=lambda: int(os.getenv("DRC_LOGIN_MAX_ATTEMPTS", "5")))
    login_lockout_minutes: int = Field(default_factory=lambda: int(os.getenv("DRC_LOGIN_LOCKOUT_MINUTES", "15")))
    password_min_length: int = Field(default_factory=lambda: int(os.getenv("DRC_PASSWORD_MIN_LENGTH", "12")))
    require_email_verification: bool = Field(
        default_factory=lambda: os.getenv("DRC_REQUIRE_EMAIL_VERIFICATION", "false").lower() == "true"
    )
    expose_dev_tokens: bool = Field(
        default_factory=lambda: os.getenv("DRC_EXPOSE_DEV_TOKENS", "false").lower() == "true"
    )
    log_level: str = Field(default_factory=lambda: os.getenv("DRC_LOG_LEVEL", "INFO").strip().upper())
    log_format: str = Field(default_factory=lambda: os.getenv("DRC_LOG_FORMAT", "json").strip().lower())
    metrics_token: str | None = Field(default_factory=lambda: os.getenv("DRC_METRICS_TOKEN") or None)
    ops_error_rate_threshold: float = Field(
        default_factory=lambda: float(os.getenv("DRC_OPS_ERROR_RATE_THRESHOLD", "0.10"))
    )
    ops_latency_threshold_ms: float = Field(
        default_factory=lambda: float(os.getenv("DRC_OPS_LATENCY_THRESHOLD_MS", "2000"))
    )
    ops_queue_depth_threshold: int = Field(
        default_factory=lambda: int(os.getenv("DRC_OPS_QUEUE_DEPTH_THRESHOLD", "25"))
    )
    ops_failed_job_threshold: int = Field(default_factory=lambda: int(os.getenv("DRC_OPS_FAILED_JOB_THRESHOLD", "5")))
    ops_alert_cooldown_minutes: int = Field(
        default_factory=lambda: int(os.getenv("DRC_OPS_ALERT_COOLDOWN_MINUTES", "30"))
    )
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
        if self.log_format not in {"json", "text"}:
            errors.append("DRC_LOG_FORMAT must be json or text.")
        if not 0 <= self.ops_error_rate_threshold <= 1:
            errors.append("DRC_OPS_ERROR_RATE_THRESHOLD must be between 0 and 1.")
        if (
            min(
                self.ops_latency_threshold_ms,
                self.ops_queue_depth_threshold,
                self.ops_failed_job_threshold,
                self.ops_alert_cooldown_minutes,
            )
            < 1
        ):
            errors.append("Operational reliability thresholds must be positive.")
        if self.password_min_length < 12:
            errors.append("DRC_PASSWORD_MIN_LENGTH must be at least 12.")
        if self.login_max_attempts < 1 or self.login_window_minutes < 1 or self.login_lockout_minutes < 1:
            errors.append("Login protection values must be positive integers.")
        if not self.allowed_hosts:
            errors.append("DRC_ALLOWED_HOSTS must contain at least one host.")
        if self.storage_backend not in {"local", "gcs"}:
            errors.append("DRC_STORAGE_BACKEND must be 'local' or 'gcs'.")
        if self.storage_backend == "gcs" and not self.gcs_bucket:
            errors.append("DRC_GCS_BUCKET is required when DRC_STORAGE_BACKEND=gcs.")
        if self.is_production:
            if self.database_url.startswith("sqlite"):
                errors.append("Production requires PostgreSQL; SQLite is not permitted.")
            if not self.csrf_enabled:
                errors.append("DRC_CSRF_ENABLED must be true in production.")
            if not self.secure_cookies:
                errors.append("DRC_SECURE_COOKIES must be true in production.")
            if "*" in self.allowed_hosts:
                errors.append("Wildcard DRC_ALLOWED_HOSTS is not permitted in production.")
            if any(origin == "*" for origin in self.cors_origins):
                errors.append("Wildcard DRC_CORS_ORIGINS is not permitted in production.")
            if self.expose_dev_tokens:
                errors.append("DRC_EXPOSE_DEV_TOKENS must be false in production.")
            if self.enable_internal_scheduler:
                errors.append("DRC_ENABLE_INTERNAL_SCHEDULER is obsolete and must remain false in production.")
            if not self.scheduler_token or len(self.scheduler_token) < 24:
                errors.append("Set DRC_SCHEDULER_TOKEN to a secret of at least 24 characters in production.")
            if self.bootstrap_admin_email in {"admin@drc.local", "admin@example.invalid"}:
                errors.append("Set a unique DRC_ADMIN_EMAIL in production.")
            if (
                self.bootstrap_admin_password in {"ChangeMe123!", "replace-with-a-strong-random-password"}
                or len(self.bootstrap_admin_password) < 16
            ):
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
