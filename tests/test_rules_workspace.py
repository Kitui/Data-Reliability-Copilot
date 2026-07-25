from pathlib import Path

def test_rules_workspace_assets_and_chartjs():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert 'id="rulesPage"' in html
    assert 'ruleCategoryChart' in html and 'failingRulesChart' in html
    assert 'new Chart' in js
    assert 'loadRulesWorkspace' in js
