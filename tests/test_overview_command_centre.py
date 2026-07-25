from pathlib import Path
from app.main import create_app

def test_overview_command_centre_ui_is_wired():
    html=Path("app/static/index.html").read_text()
    js=Path("app/static/app.js").read_text()
    css=Path("app/static/styles.css").read_text()
    assert "Data Reliability Command Centre" in html
    assert 'id="overviewPlatformSummary"' in html
    assert 'id="overviewUpcomingAudits"' in html
    assert "Top Affected Columns" not in html.split('id="overviewPage"',1)[1].split('id="datasetsPage"',1)[0]
    assert "loadOverviewCommandCentre" in js
    assert ".command-ribbon" in css

def test_overview_command_centre_route_registered():
    assert "/reports/overview" in {route.path for route in create_app().routes}
