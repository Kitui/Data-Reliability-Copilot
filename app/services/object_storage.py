from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.config import Settings, get_settings


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int


class ObjectStorage(ABC):
    @abstractmethod
    def put_bytes(self, key: str, content: bytes) -> StoredObject: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise StorageError("Storage key escapes the configured root.")
        return candidate

    def put_bytes(self, key: str, content: bytes) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredObject(key=key, size_bytes=len(content))

    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"Object not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class GCSObjectStorage(ObjectStorage):
    def __init__(self, bucket_name: str) -> None:
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise StorageError("google-cloud-storage is required for the GCS backend.") from exc
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def put_bytes(self, key: str, content: bytes) -> StoredObject:
        self.bucket.blob(key).upload_from_string(content)
        return StoredObject(key=key, size_bytes=len(content))

    def get_bytes(self, key: str) -> bytes:
        blob = self.bucket.blob(key)
        if not blob.exists(self.client):
            raise StorageError(f"Object not found: {key}")
        return blob.download_as_bytes()

    def delete(self, key: str) -> None:
        blob = self.bucket.blob(key)
        if blob.exists(self.client):
            blob.delete()

    def exists(self, key: str) -> bool:
        return self.bucket.blob(key).exists(self.client)


def build_object_storage(settings: Settings | None = None) -> ObjectStorage:
    settings = settings or get_settings()
    if settings.storage_backend == "gcs":
        if not settings.gcs_bucket:
            raise StorageError("GCS bucket is not configured.")
        return GCSObjectStorage(settings.gcs_bucket)
    return LocalObjectStorage(settings.data_dir)
