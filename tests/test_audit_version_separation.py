from pathlib import Path


def test_versioning_helper_exists_and_routes_use_lineage():
    helper = Path("app/versioning.py").read_text()
    datasets = Path("app/api/routes/datasets.py").read_text()
    drift = Path("app/api/routes/schema_drift.py").read_text()
    assert "def lineage_audits" in helper
    assert "audits = lineage_audits(audits)" in datasets
    assert "audits = lineage_audits(audits)" in drift


def test_audit_result_tracks_kind_and_dataset_version():
    schemas = Path("app/schemas.py").read_text()
    audits = Path("app/api/routes/audits.py").read_text()
    handlers = Path("app/jobs/handlers.py").read_text()
    assert "audit_kind:" in schemas
    assert "dataset_version:" in schemas
    assert 'result.audit_kind = "rerun"' in audits
    assert 'result.audit_kind = "scheduled"' in handlers
