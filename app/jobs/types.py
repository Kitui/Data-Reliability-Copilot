from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    VALIDATING = "validating"
    PROCESSING = "processing"
    SCORING = "scoring"
    GENERATING_OUTPUT = "generating_output"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    DATASET_IMPORT = "dataset_audit"
    DATASET_AUDIT = "dataset_audit"
    CONTRACT_VALIDATION = "contract_validation"
    REMEDIATION = "remediation"
    REPORT_GENERATION = "report_generation"
    CONNECTOR_SYNC = "connector_sync"
    SCHEDULED_AUDIT = "scheduled_audit"
