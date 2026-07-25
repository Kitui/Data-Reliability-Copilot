from pathlib import Path


def test_contract_findings_render_below_registry_with_six_row_pagination():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'id="contractValidationRegistry"' in html
    assert "contractFindingPageSize:6" in js
    assert "function renderContractFindings" in js
    assert "data-contract-findings-page" in js
    assert "contract-validation-registry" in css
