from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.jobs.types import JobType


@dataclass(frozen=True)
class JobContext:
    job_id: int
    workspace_id: int
    job_type: JobType
    payload: dict[str, Any]


class JobHandler(ABC):
    """Interface implemented by background job handlers."""

    @abstractmethod
    def execute(self, context: JobContext) -> dict[str, Any]: ...


class JobDispatcher(ABC):
    """Transport-neutral interface for Cloud Tasks, Pub/Sub, or local queues."""

    @abstractmethod
    def enqueue(self, job_id: int, *, idempotency_key: str) -> None: ...
