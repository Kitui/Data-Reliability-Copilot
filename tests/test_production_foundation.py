from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import ConfigurationError, Settings
from app.jobs.types import JobStatus, JobType
from app.services.object_storage import LocalObjectStorage, StorageError


def test_production_configuration_rejects_unsafe_defaults(monkeypatch):
    monkeypatch.setenv("DRC_ENVIRONMENT", "production")
    monkeypatch.setenv("DRC_DATABASE_URL", "sqlite:///unsafe.db")
    monkeypatch.setenv("DRC_SECURE_COOKIES", "false")
    monkeypatch.setenv("DRC_ENABLE_INTERNAL_SCHEDULER", "true")
    settings = Settings()
    with pytest.raises(ConfigurationError):
        settings.validate_runtime_configuration()


def test_local_object_storage_round_trip(tmp_path: Path):
    storage = LocalObjectStorage(tmp_path)
    stored = storage.put_bytes("uploads/example.csv", b"a,b\n1,2\n")
    assert stored.size_bytes == 8
    assert storage.exists(stored.key)
    assert storage.get_bytes(stored.key) == b"a,b\n1,2\n"
    storage.delete(stored.key)
    assert not storage.exists(stored.key)


def test_local_object_storage_blocks_path_escape(tmp_path: Path):
    storage = LocalObjectStorage(tmp_path)
    with pytest.raises(StorageError):
        storage.put_bytes("../escape.txt", b"no")


def test_background_job_enums_are_stable():
    assert JobStatus.QUEUED == "queued"
    assert JobType.DATASET_AUDIT == "dataset_audit"
