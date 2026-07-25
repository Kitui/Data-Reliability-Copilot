from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.observability import MetricsRegistry
from app.main import create_app


def test_metrics_registry_exports_prometheus():
    registry = MetricsRegistry()
    registry.begin()
    registry.finish("/health/live", 200, 12.5)
    text = registry.prometheus()
    assert "drc_http_requests_total 1" in text
    assert 'drc_http_responses_total{status="200"} 1' in text


def test_liveness_and_readiness():
    with TestClient(create_app()) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "ok"
        ready = client.get("/health/ready")
        assert ready.status_code in {200, 503}
        assert "checks" in ready.json()


def test_metrics_endpoint():
    with TestClient(create_app()) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "drc_http_requests_total" in response.text
