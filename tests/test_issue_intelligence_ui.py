from pathlib import Path


def test_all_issue_types_receive_structured_issue_intelligence():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert "renderGeneralIssueIntelligenceV2" in script
    assert "Issue intelligence" in script
    assert "Business impact" in script
    assert "Likely root cause" in script
    assert "Recommended action" in script
    assert ".issue-intelligence-panel" in styles
    assert "minmax(340px,25%)" in styles
