from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.schemas import UploadedFileInfo
from app.services.object_storage import ObjectStorage, StorageError, build_object_storage

_ALLOWED_EXTENSIONS = {".csv"}
_ALLOWED_CONTENT_TYPES = {
    None,
    "",
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class DatasetFileError(ValueError):
    """Raised when a dataset file is unsafe, invalid, or unavailable."""


@dataclass(frozen=True)
class DatasetFileService:
    storage: ObjectStorage
    settings: Settings

    def validate_upload(self, content: bytes, original_filename: str, content_type: str | None) -> str:
        filename = Path(original_filename or "uploaded.csv").name
        extension = Path(filename).suffix.lower()
        if extension not in _ALLOWED_EXTENSIONS:
            raise DatasetFileError("Only CSV files are supported.")
        if content_type not in _ALLOWED_CONTENT_TYPES:
            raise DatasetFileError("The uploaded file type is not supported.")
        if not content:
            raise DatasetFileError("The selected CSV file is empty.")
        if len(content) > self.settings.max_upload_bytes:
            limit_mb = max(1, self.settings.max_upload_bytes // (1024 * 1024))
            raise DatasetFileError(f"The CSV exceeds the {limit_mb} MB upload limit.")
        if b"\x00" in content[:8192]:
            raise DatasetFileError("The uploaded file does not appear to be a valid text CSV.")
        return filename

    def save_upload(
        self,
        content: bytes,
        original_filename: str,
        content_type: str | None,
        workspace_id: int,
        category: str = "uploads",
    ) -> UploadedFileInfo:
        filename = self.validate_upload(content, original_filename, content_type)
        extension = Path(filename).suffix.lower()
        stored_filename = f"{uuid4()}{extension}"
        safe_name = _SAFE_FILENAME.sub("_", Path(filename).stem).strip("._-")[:80] or "dataset"
        key = f"workspaces/{int(workspace_id)}/{category}/{stored_filename}"
        self.storage.put_bytes(key, content)
        return UploadedFileInfo(
            original_filename=filename,
            stored_filename=stored_filename,
            path=key,
            size_bytes=len(content),
            content_type=content_type or "text/csv",
            storage_backend=self.settings.storage_backend,
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            display_name=f"{safe_name}{extension}",
        )

    def _legacy_path(self, key: str) -> Path:
        """Resolve a pre-Feature-26 local upload key without allowing traversal."""
        root = self.settings.data_dir.resolve()
        candidate = (root / key).resolve()
        if candidate != root and root not in candidate.parents:
            raise DatasetFileError("The stored dataset key is invalid.")
        return candidate

    def read_bytes(self, key: str) -> bytes:
        try:
            if self.storage.exists(key):
                return self.storage.get_bytes(key)
        except StorageError:
            pass

        # Development compatibility for records created before GCS was enabled.
        legacy = self._legacy_path(key)
        if legacy.is_file():
            return legacy.read_bytes()
        raise DatasetFileError("The source dataset file is unavailable.")

    def delete(self, key: str) -> None:
        deleted = False
        try:
            if self.storage.exists(key):
                self.storage.delete(key)
                deleted = True
        except StorageError as exc:
            raise DatasetFileError("The source dataset file could not be deleted.") from exc

        legacy = self._legacy_path(key)
        if legacy.is_file():
            legacy.unlink()
            deleted = True

        # Missing objects are treated as already deleted, making cleanup idempotent.
        _ = deleted

    def exists(self, key: str) -> bool:
        try:
            if self.storage.exists(key):
                return True
        except StorageError:
            pass
        return self._legacy_path(key).is_file()


def build_dataset_file_service(settings: Settings | None = None) -> DatasetFileService:
    resolved = settings or get_settings()
    return DatasetFileService(build_object_storage(resolved), resolved)
