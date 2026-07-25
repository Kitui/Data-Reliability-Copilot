from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AuditRecord, IssueRecord, UploadRecord
from app.db.session import create_database_engine
from app.schemas import AuditListItem, AuditResult


class AuditStore:
    """Database-backed audit repository.

    A directory path creates ``drc.db`` inside that directory for backward
    compatibility with Feature 01 tests and integrations. A ``.db`` path uses
    that file directly.
    """

    def __init__(self, location: Path | str) -> None:
        raw = Path(location)
        database_path = raw if raw.suffix == ".db" else raw / "drc.db"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self.engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
        from app.db.session import Base
        from app.db import models  # noqa: F401

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    @classmethod
    def from_session_factory(cls, factory: sessionmaker[Session]) -> "AuditStore":
        instance = cls.__new__(cls)
        instance.database_path = None
        instance.engine = factory.kw["bind"]
        instance.session_factory = factory
        return instance

    def save(self, audit: AuditResult, workspace_id: int | None = None) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory.begin() as session:
            record = session.get(AuditRecord, audit.audit_id)
            if record is None:
                record = AuditRecord(audit_id=audit.audit_id, created_at=audit.created_at, updated_at=now)
                session.add(record)
            record.workspace_id = workspace_id if workspace_id is not None else record.workspace_id
            record.dataset_name = audit.dataset_name
            record.created_at = audit.created_at
            record.score = audit.score.overall
            record.risk_level = audit.summary.risk_level
            record.issue_count = len(audit.issues)
            record.summary_source = audit.summary.source
            record.payload_json = audit.model_dump_json()
            record.updated_at = now

            session.execute(delete(IssueRecord).where(IssueRecord.audit_id == audit.audit_id))
            for issue in audit.issues:
                session.add(IssueRecord(
                    audit_id=audit.audit_id,
                    issue_id=issue.id,
                    category=issue.category,
                    severity=issue.severity,
                    status=issue.status,
                    title=issue.title,
                    owner=issue.owner,
                    affected_rows=issue.affected_rows,
                    affected_rate=issue.affected_rate,
                ))

            session.execute(delete(UploadRecord).where(UploadRecord.audit_id == audit.audit_id))
            if audit.upload is not None:
                session.add(UploadRecord(
                    audit_id=audit.audit_id,
                    original_filename=audit.upload.original_filename,
                    stored_filename=audit.upload.stored_filename,
                    relative_path=audit.upload.path,
                    size_bytes=audit.upload.size_bytes,
                    content_type=audit.upload.content_type,
                ))

    def get(self, audit_id: str, workspace_id: int | None = None) -> AuditResult | None:
        with self.session_factory() as session:
            statement = select(AuditRecord.payload_json).where(AuditRecord.audit_id == audit_id)
            if workspace_id is not None: statement = statement.where(AuditRecord.workspace_id == workspace_id)
            payload = session.scalar(statement)
            return AuditResult.model_validate_json(payload) if payload else None

    def list(self, workspace_id: int | None = None) -> list[AuditListItem]:
        statement = select(AuditRecord).order_by(AuditRecord.created_at.desc())
        if workspace_id is not None: statement = statement.where(AuditRecord.workspace_id == workspace_id)
        with self.session_factory() as session:
            records = session.scalars(statement).all()
            return [AuditListItem(
                audit_id=record.audit_id,
                dataset_name=record.dataset_name,
                created_at=record.created_at,
                score=record.score,
                risk_level=record.risk_level,
                issue_count=record.issue_count,
                summary_source=record.summary_source,
            ) for record in records]

    def delete(self, audit_id: str, workspace_id: int | None = None) -> bool:
        with self.session_factory.begin() as session:
            record = session.get(AuditRecord, audit_id)
            if record is None or (workspace_id is not None and record.workspace_id != workspace_id):
                return False
            session.delete(record)
            return True

    def count(self) -> int:
        with self.session_factory() as session:
            return len(session.scalars(select(AuditRecord.audit_id)).all())
