from pathlib import Path

from sqlalchemy import inspect, select

from app.auditor import audit_dataframe
from app.db.models import AuditRecord, IssueRecord, UploadRecord
from app.ingestion import read_csv_path
from app.schemas import UploadedFileInfo
from app.storage import AuditStore


def test_database_store_creates_normalized_records(tmp_path: Path) -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    upload = UploadedFileInfo(
        original_filename="customers_dirty.csv",
        stored_filename="stored.csv",
        path="data/uploads/stored.csv",
        size_bytes=250,
        content_type="text/csv",
    )
    audit = audit_dataframe(frame, "customers_dirty.csv", upload=upload)
    store = AuditStore(tmp_path / "test.db")

    store.save(audit)

    with store.session_factory() as session:
        record = session.get(AuditRecord, audit.audit_id)
        issues = session.scalars(select(IssueRecord).where(IssueRecord.audit_id == audit.audit_id)).all()
        saved_upload = session.scalar(select(UploadRecord).where(UploadRecord.audit_id == audit.audit_id))

    assert record is not None
    assert record.score == audit.score.overall
    assert len(issues) == len(audit.issues)
    assert saved_upload is not None
    assert saved_upload.original_filename == "customers_dirty.csv"


def test_database_store_updates_issue_workflow_without_duplicates(tmp_path: Path) -> None:
    audit = audit_dataframe(read_csv_path(Path("samples/customers_dirty.csv")), "customers_dirty.csv")
    store = AuditStore(tmp_path)
    store.save(audit)
    audit.issues[0].status = "in_progress"
    audit.issues[0].owner = "Data Steward"
    store.save(audit)

    loaded = store.get(audit.audit_id)
    assert loaded is not None
    assert loaded.issues[0].status == "in_progress"
    assert loaded.issues[0].owner == "Data Steward"
    with store.session_factory() as session:
        issue_count = len(session.scalars(select(IssueRecord).where(IssueRecord.audit_id == audit.audit_id)).all())
    assert issue_count == len(audit.issues)


def test_database_schema_contains_feature_two_tables(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "schema.db")
    tables = set(inspect(store.engine).get_table_names())
    assert {"audits", "audit_issues", "uploads"}.issubset(tables)


def test_database_store_delete_and_count(tmp_path: Path) -> None:
    audit = audit_dataframe(read_csv_path(Path("samples/customers_dirty.csv")), "customers_dirty.csv")
    store = AuditStore(tmp_path)
    store.save(audit)
    assert store.count() == 1
    assert store.delete(audit.audit_id) is True
    assert store.count() == 0
    assert store.delete(audit.audit_id) is False
