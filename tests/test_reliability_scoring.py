from app.auditor import audit_dataframe
from app.schemas import QualityIssue, ScoringContext
from app.scoring import score_audit
import pandas as pd


def issue(issue_id: str, severity: str, rate: float, status: str = "open", rule_id=None):
    return QualityIssue(
        id=issue_id,
        category="validity",
        severity=severity,
        title="Test issue",
        detail="Test issue",
        columns=["value"],
        affected_rows=max(1, int(rate * 100)),
        affected_rate=rate,
        examples=[],
        recommendation="Fix it",
        confidence=1.0,
        status=status,
        rule_id=rule_id,
    )


def test_scoring_uses_severity_breadth_and_criticality():
    result = audit_dataframe(pd.DataFrame({"value": list(range(100))}), "scores.csv")
    low = score_audit(result.profile, [issue("a", "low", 0.05)], ScoringContext(dataset_criticality="low"))
    broad = score_audit(result.profile, [issue("b", "critical", 0.8)], ScoringContext(dataset_criticality="mission_critical"))
    assert broad.overall < low.overall
    assert broad.total_weighted_penalty > low.total_weighted_penalty
    assert broad.deductions[0].reason


def test_fixed_ignored_and_accepted_risk_are_handled_differently():
    result = audit_dataframe(pd.DataFrame({"value": list(range(100))}), "scores.csv")
    open_score = score_audit(result.profile, [issue("a", "high", 0.5)])
    accepted = score_audit(result.profile, [issue("a", "high", 0.5, "accepted_risk")])
    fixed = score_audit(result.profile, [issue("a", "high", 0.5, "fixed")])
    assert open_score.overall < accepted.overall <= fixed.overall
    assert accepted.accepted_risk_count == 1
    assert fixed.active_issue_count == 0


def test_rule_backed_findings_receive_rule_multiplier():
    result = audit_dataframe(pd.DataFrame({"value": list(range(100))}), "scores.csv")
    standard = score_audit(result.profile, [issue("a", "medium", 0.4)])
    rule_backed = score_audit(result.profile, [issue("b", "medium", 0.4, rule_id=5)])
    assert rule_backed.overall <= standard.overall
    assert rule_backed.deductions[0].weighted_penalty > standard.deductions[0].weighted_penalty


def test_score_breakdown_and_recalculation_api():
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app()) as client:
        assert client.post('/auth/login', json={'email': 'admin@drc.local', 'password': 'ChangeMe123!'}).status_code == 200
        audit = client.post('/audits/sample').json()
        breakdown = client.get(f"/audits/{audit['audit_id']}/score-breakdown")
        assert breakdown.status_code == 200
        assert breakdown.json()['score']['dimension_weights']
        recalculated = client.post(
            f"/audits/{audit['audit_id']}/score/recalculate",
            json={'dataset_criticality': 'mission_critical'},
        )
        assert recalculated.status_code == 200
        assert recalculated.json()['scoring_context']['dataset_criticality'] == 'mission_critical'
        assert recalculated.json()['score']['dataset_criticality'] == 'mission_critical'
