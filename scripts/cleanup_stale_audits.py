from __future__ import annotations

from sqlalchemy import select

from app.db.models import AuditRecord, DatasetRecord, UploadRecord
from app.db.session import get_session_factory
from app.services.dataset_files import build_dataset_file_service


def main() -> None:
    Session = get_session_factory()
    files = build_dataset_file_service()
    removed = 0

    with Session() as db:
        audits = list(db.scalars(select(AuditRecord)).all())
        for audit in audits:
            upload = db.scalar(select(UploadRecord).where(UploadRecord.audit_id == audit.audit_id))
            if upload is not None and files.exists(upload.relative_path):
                continue
            db.delete(audit)
            removed += 1

        datasets = list(db.scalars(select(DatasetRecord)).all())
        for dataset in datasets:
            latest = db.scalar(
                select(AuditRecord)
                .where(
                    AuditRecord.workspace_id == dataset.workspace_id,
                    AuditRecord.dataset_name == dataset.name,
                )
                .order_by(AuditRecord.created_at.desc())
            )
            dataset.latest_audit_id = latest.audit_id if latest else None
            if latest is None:
                dataset.record_count = 0
                dataset.column_count = 0
                dataset.quality_score = None
                dataset.issue_count = 0
                dataset.status = "registered"

        db.commit()

    print(f"Removed {removed} stale audit record(s).")


if __name__ == "__main__":
    main()
