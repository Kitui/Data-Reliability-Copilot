from pathlib import Path
import sys
import types

import pytest

from app.auditor import audit_dataframe
from app.analyst import answer_question
from app.comparison import compare_audits
from app.contracts import contract_to_rule_config, generate_contract
from app.ingestion import read_csv_path
from app.ml_readiness import assess_ml_readiness
from app.reports import build_html_report, build_markdown_report
from app.remediation import build_remediation_plan
from app.schemas import AuditRuleConfig, LlmAuditSummary, UploadedFileInfo
from app.storage import AuditStore


@pytest.fixture(autouse=True)
def disable_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_sample_audit_detects_expected_issues() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    issue_titles = {issue.title for issue in result.issues}

    assert result.profile.row_count == 10
    assert result.score.overall < 100
    assert "Duplicate rows detected" in issue_titles
    assert "Duplicate key values in customer_id" in issue_titles
    assert "Potential PII columns detected" in issue_titles
    assert any("Invalid email format" in title for title in issue_titles)
    assert any("Outliers detected" in title for title in issue_titles)
    assert result.summary.risk_level in {"medium", "high", "critical"}


def test_llm_context_excludes_examples() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    top_issues = result.summary.llm_ready_context["top_issues"]

    assert top_issues
    assert "examples" not in top_issues[0]


def test_audit_store_persists_and_lists_results(tmp_path: Path) -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")
    store = AuditStore(tmp_path)

    store.save(result)
    loaded = store.get(result.audit_id)
    listed = store.list()

    assert loaded is not None
    assert loaded.audit_id == result.audit_id
    assert loaded.score.overall == result.score.overall
    assert listed[0].audit_id == result.audit_id
    assert listed[0].issue_count == len(result.issues)
    assert listed[0].summary_source == result.summary.source


def test_rule_based_summary_is_default_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    assert result.summary.source == "rule_based"
    assert result.summary.model is None
    assert result.summary.remediation_plan


def test_llm_summary_contract_rejects_unexpected_fields() -> None:
    with pytest.raises(ValueError):
        LlmAuditSummary.model_validate(
            {
                "executive_summary": "This dataset has enough detail for an executive summary response.",
                "recommended_focus": ["Fix invalid emails"],
                "risk_level": "high",
                "notable_patterns": ["Invalid contact data"],
                "remediation_plan": ["Normalize and validate contact fields"],
                "confidence": 0.9,
                "invented_metric": "not allowed",
            }
        )


def test_configured_rules_detect_schema_and_value_violations() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    config = AuditRuleConfig(
        required_columns=["customer_id", "segment"],
        unique_columns=["customer_id"],
        allowed_values={"status": ["Active", "Inactive"]},
        numeric_ranges={"monthly_spend": {"min": 0, "max": 1000}},
    )

    result = audit_dataframe(frame, "customers_dirty.csv", rule_config=config)
    titles = {issue.title for issue in result.issues}

    assert "Required column missing: segment" in titles
    assert "Configured unique column has duplicates: customer_id" in titles
    assert "Values outside allowed set in status" in titles
    assert "Configured numeric range violated in monthly_spend" in titles
    assert result.rule_config.required_columns == ["customer_id", "segment"]


def test_audit_result_can_store_upload_metadata() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    upload = UploadedFileInfo(
        original_filename="customers_dirty.csv",
        stored_filename="abc.csv",
        path="data/uploads/abc.csv",
        size_bytes=100,
        content_type="text/csv",
    )

    result = audit_dataframe(frame, "customers_dirty.csv", upload=upload)

    assert result.upload is not None
    assert result.upload.path == "data/uploads/abc.csv"


def test_markdown_report_contains_summary_and_issues() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    report = build_markdown_report(result)

    assert "# Data Quality Audit: customers_dirty.csv" in report
    assert "## Score Breakdown" in report
    assert "Duplicate rows detected" in report


def test_html_report_explains_score_breakdown() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    report = build_html_report(result)

    assert "<!doctype html>" in report
    assert "How much required data is present instead of blank." in report
    assert "Duplicate rows detected" in report


def test_remediation_plan_generates_actions_and_script() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    plan = build_remediation_plan(result)

    assert plan.actions
    assert "pd.read_csv" in plan.generated_cleaning_script
    assert any(action.action_type == "deduplicate" for action in plan.actions)
    assert "drop_duplicates(, subset=" not in plan.generated_cleaning_script
    assert "drop_duplicates(subset=['customer_id'])" in plan.generated_cleaning_script


def test_contract_generation_can_be_reused_as_rule_config() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    contract = generate_contract(result)
    config = contract_to_rule_config(contract)

    assert contract.required_columns
    assert "status" in contract.allowed_values
    assert config.required_columns == contract.required_columns


def test_comparison_tracks_score_and_issue_changes() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    baseline = audit_dataframe(frame.head(6).copy(), "baseline.csv")
    candidate = audit_dataframe(frame, "candidate.csv")

    comparison = compare_audits(baseline, candidate)

    assert comparison.baseline_audit_id == baseline.audit_id
    assert comparison.candidate_audit_id == candidate.audit_id
    assert isinstance(comparison.score_delta, int)
    assert comparison.issue_count_delta != 0


def test_ml_readiness_identifies_blockers_or_warnings() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    readiness = assess_ml_readiness(result)

    assert readiness.score <= result.score.overall
    assert readiness.blockers or readiness.warnings
    assert "customer_id" in readiness.unsuitable_features


def test_analyst_answer_uses_audit_context() -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    answer = answer_question(result, "What should I fix first?")

    assert answer.audit_id == result.audit_id
    assert "deduplicate" in answer.answer.lower()
    assert answer.supporting_issue_ids


def test_analyst_can_use_llm_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = read_csv_path(Path("samples/customers_dirty.csv"))
    result = audit_dataframe(frame, "customers_dirty.csv")

    class FakeCompletions:
        def create(self, **kwargs: object) -> object:
            assert "messages" in kwargs
            message = types.SimpleNamespace(content="Focus on duplicate customer IDs before model training.")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    answer = answer_question(result, "Can I use this for model training?")

    assert answer.source == "llm"
    assert "duplicate customer IDs" in answer.answer
    assert answer.supporting_issue_ids
