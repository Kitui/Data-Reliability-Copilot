from __future__ import annotations

from unittest.mock import Mock, patch

from app.services.object_storage import GCSObjectStorage
from app.services.operational_reliability import storage_check


def test_gcs_readiness_uses_object_listing_not_bucket_metadata():
    storage = GCSObjectStorage.__new__(GCSObjectStorage)
    storage.client = Mock()
    storage.bucket = Mock()
    storage.bucket.name = "drc-test-bucket"
    storage.client.list_blobs.return_value = iter([])

    with patch("app.services.operational_reliability.build_object_storage", return_value=storage):
        ok, detail = storage_check()

    assert ok is True
    assert detail == "ok"
    storage.client.list_blobs.assert_called_once_with("drc-test-bucket", max_results=1)
    storage.bucket.exists.assert_not_called()


def test_gcs_readiness_reports_forbidden_without_exposing_message():
    storage = GCSObjectStorage.__new__(GCSObjectStorage)
    storage.client = Mock()
    storage.bucket = Mock()
    storage.bucket.name = "drc-test-bucket"
    storage.client.list_blobs.side_effect = PermissionError("sensitive details")

    with patch("app.services.operational_reliability.build_object_storage", return_value=storage):
        ok, detail = storage_check()

    assert ok is False
    assert detail == "PermissionError"
