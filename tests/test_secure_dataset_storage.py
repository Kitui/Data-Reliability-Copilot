from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.dataset_files import DatasetFileError, DatasetFileService
from app.services.object_storage import LocalObjectStorage, StorageError


def make_service(tmp_path: Path, max_bytes: int = 1024) -> DatasetFileService:
    settings = Settings(
        environment="testing",
        storage_backend="local",
        max_upload_bytes=max_bytes,
        root_dir=tmp_path,
    )
    return DatasetFileService(LocalObjectStorage(tmp_path / "objects"), settings)


def test_upload_uses_workspace_isolated_key_and_checksum(tmp_path: Path):
    service = make_service(tmp_path)
    content = b"id,name\n1,Alice\n"

    upload = service.save_upload(content, "../../Customer Export.csv", "text/csv", workspace_id=42)

    assert upload.path.startswith("workspaces/42/uploads/")
    assert upload.path.endswith(".csv")
    assert upload.original_filename == "Customer Export.csv"
    assert upload.display_name == "Customer_Export.csv"
    assert upload.checksum_sha256
    assert service.read_bytes(upload.path) == content


def test_rejects_non_csv_empty_binary_and_oversized_files(tmp_path: Path):
    service = make_service(tmp_path, max_bytes=10)

    with pytest.raises(DatasetFileError, match="Only CSV"):
        service.save_upload(b"abc", "data.xlsx", "application/octet-stream", 1)
    with pytest.raises(DatasetFileError, match="empty"):
        service.save_upload(b"", "data.csv", "text/csv", 1)
    with pytest.raises(DatasetFileError, match="upload limit"):
        service.save_upload(b"a" * 11, "data.csv", "text/csv", 1)
    with pytest.raises(DatasetFileError, match="valid text CSV"):
        service.save_upload(b"id\x00name", "data.csv", "text/csv", 1)


def test_local_storage_blocks_path_traversal(tmp_path: Path):
    storage = LocalObjectStorage(tmp_path / "objects")
    with pytest.raises(StorageError, match="escapes"):
        storage.put_bytes("../../secret.csv", b"secret")


def test_delete_removes_object(tmp_path: Path):
    service = make_service(tmp_path)
    upload = service.save_upload(b"id\n1\n", "data.csv", "text/csv", 7)
    assert service.exists(upload.path)
    service.delete(upload.path)
    assert not service.exists(upload.path)


def test_gcs_mode_can_read_and_remove_legacy_local_uploads(tmp_path: Path):
    class EmptyRemoteStorage:
        def put_bytes(self, key: str, content: bytes):
            raise AssertionError("not used")

        def get_bytes(self, key: str) -> bytes:
            raise StorageError("missing")

        def delete(self, key: str) -> None:
            raise StorageError("missing")

        def exists(self, key: str) -> bool:
            return False

    settings = Settings(
        environment="testing",
        storage_backend="gcs",
        gcs_bucket="test-bucket",
        root_dir=tmp_path,
    )
    legacy = settings.data_dir / "uploads" / "legacy.csv"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(b"id,name\n1,Alice\n")
    service = DatasetFileService(EmptyRemoteStorage(), settings)  # type: ignore[arg-type]

    assert service.exists("uploads/legacy.csv")
    assert service.read_bytes("uploads/legacy.csv") == b"id,name\n1,Alice\n"
    service.delete("uploads/legacy.csv")
    assert not legacy.exists()
