from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Emit one structured JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": get_settings().service_name,
            "environment": get_settings().environment,
        }
        for field in (
            "request_id", "workspace_id", "user_id", "job_id", "audit_id",
            "route", "method", "status_code", "duration_ms", "error_type",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root.setLevel(level)
    if settings.log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.setFormatter(formatter)


@dataclass
class MetricSnapshot:
    request_total: int
    error_total: int
    active_requests: int
    latency_sum_ms: float
    status_counts: dict[str, int]
    route_counts: dict[str, int]


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_total = 0
        self._error_total = 0
        self._active_requests = 0
        self._latency_sum_ms = 0.0
        self._status_counts: dict[str, int] = defaultdict(int)
        self._route_counts: dict[str, int] = defaultdict(int)

    def begin(self) -> None:
        with self._lock:
            self._active_requests += 1

    def finish(self, route: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self._request_total += 1
            self._latency_sum_ms += duration_ms
            self._status_counts[str(status_code)] += 1
            self._route_counts[route] += 1
            if status_code >= 500:
                self._error_total += 1

    def snapshot(self) -> MetricSnapshot:
        with self._lock:
            return MetricSnapshot(
                request_total=self._request_total,
                error_total=self._error_total,
                active_requests=self._active_requests,
                latency_sum_ms=self._latency_sum_ms,
                status_counts=dict(self._status_counts),
                route_counts=dict(self._route_counts),
            )

    def prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            "# HELP drc_http_requests_total Total HTTP requests.",
            "# TYPE drc_http_requests_total counter",
            f"drc_http_requests_total {snap.request_total}",
            "# HELP drc_http_errors_total Total HTTP 5xx responses.",
            "# TYPE drc_http_errors_total counter",
            f"drc_http_errors_total {snap.error_total}",
            "# HELP drc_http_active_requests Current active HTTP requests.",
            "# TYPE drc_http_active_requests gauge",
            f"drc_http_active_requests {snap.active_requests}",
            "# HELP drc_http_request_duration_milliseconds_sum Cumulative request duration.",
            "# TYPE drc_http_request_duration_milliseconds_sum counter",
            f"drc_http_request_duration_milliseconds_sum {snap.latency_sum_ms:.3f}",
        ]
        for status, value in sorted(snap.status_counts.items()):
            lines.append(f'drc_http_responses_total{{status="{status}"}} {value}')
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
logger = logging.getLogger("drc.request")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        metrics.begin()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            status_code = response.status_code if response is not None else 500
            route = request.scope.get("route")
            route_name = getattr(route, "path", request.url.path)
            metrics.finish(route_name, status_code, duration_ms)
            logger.info(
                "http_request",
                extra={
                    "request_id": getattr(request.state, "request_id", request.headers.get("x-request-id")),
                    "route": route_name,
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 3),
                },
            )
