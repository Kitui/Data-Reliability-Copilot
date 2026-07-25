from app.main import create_app

def test_reports_ui_is_wired():
    html=(__import__('pathlib').Path(__file__).parents[1]/'app/static/index.html').read_text()
    assert 'id="reportsPage"' in html
    assert 'Dataset Reliability Ranking' in html
    assert 'Remediation Impact' in html
    assert 'Score vs Issue Count' in html

def test_reports_routes_registered():
    paths = create_app().openapi()["paths"]
    assert '/reports' in paths
    assert '/reports/schedules' in paths
    assert '/reports/export/{format}' in paths
