from __future__ import annotations

from io import BytesIO, StringIO
import csv
from pathlib import Path

import pandas as pd


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class IngestionError(ValueError):
    """Raised when an uploaded dataset cannot be parsed safely."""


def read_csv_bytes(content: bytes, filename: str) -> pd.DataFrame:
    if not filename.lower().endswith(".csv"):
        raise IngestionError("Only CSV files are supported in the MVP.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise IngestionError("CSV file is larger than the 20 MB MVP limit.")
    if not content.strip():
        raise IngestionError("CSV file is empty.")

    # Validate the raw header before pandas normalizes duplicate names.
    decoded = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            decoded = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise IngestionError("CSV encoding is not supported. Use UTF-8 or Latin-1.")
    try:
        header = next(csv.reader(StringIO(decoded)))
    except (csv.Error, StopIteration) as exc:
        raise IngestionError(f"CSV header could not be parsed: {exc}") from exc
    normalized = [str(value).strip() for value in header]
    if not normalized or all(not value for value in normalized):
        raise IngestionError("CSV must contain a header row.")
    empty_headers = [str(index + 1) for index, value in enumerate(normalized) if not value]
    if empty_headers:
        raise IngestionError(f"CSV contains unnamed columns at positions: {', '.join(empty_headers)}.")
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    if duplicates:
        raise IngestionError(f"CSV contains duplicate column names: {', '.join(duplicates)}.")

    try:
        frame = pd.read_csv(BytesIO(content))
    except UnicodeDecodeError:
        frame = pd.read_csv(BytesIO(content), encoding="latin-1")
    except Exception as exc:
        raise IngestionError(f"CSV could not be parsed: {exc}") from exc

    return validate_frame(frame)


def read_csv_path(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise IngestionError(f"Dataset does not exist: {path}")
    return validate_frame(pd.read_csv(path))


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise IngestionError("Dataset has no rows.")
    if len(frame.columns) == 0:
        raise IngestionError("Dataset has no columns.")

    frame = frame.copy()
    frame.columns = [str(column).strip() or f"unnamed_{index}" for index, column in enumerate(frame.columns)]
    return frame
