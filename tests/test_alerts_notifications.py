from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post('/auth/login', json={'email':'admin@drc.local','password':'ChangeMe123!'})
    assert response.status_code == 200


def test_alert_dashboard_lifecycle_and_workspace_scope() -> None:
    with TestClient(create_app()) as client:
        login(client)
        assert client.post('/audits/sample').status_code == 200
        response = client.get('/alerts')
        assert response.status_code == 200
        payload = response.json()
        assert {'alerts','metrics','datasets','pagination'} <= payload.keys()
        assert payload['metrics']['total'] >= 1
        alert = payload['alerts'][0]
        assert client.patch(f"/alerts/{alert['id']}", json={'action':'acknowledge'}).json()['status'] == 'acknowledged'
        assert client.patch(f"/alerts/{alert['id']}", json={'action':'resolve'}).json()['status'] == 'resolved'
        assert client.get('/alerts/export.csv').status_code == 200


def test_notification_preferences_persist() -> None:
    with TestClient(create_app()) as client:
        login(client)
        response = client.put('/alerts/preferences/me', json={
            'in_app_enabled': True, 'email_enabled': True,
            'critical_enabled': True, 'high_enabled': True,
            'medium_enabled': False, 'low_enabled': False,
            'score_threshold': 90,
        })
        assert response.status_code == 200
        saved = client.get('/alerts/preferences/me').json()
        assert saved['email_enabled'] is True
        assert saved['score_threshold'] == 90


def test_alerts_ui_is_wired() -> None:
    with TestClient(create_app()) as client:
        html = client.get('/').text
        assert 'Alerts &amp; Notifications' in html
        assert 'alertDetailPanel' in html
        assert 'Notification preferences' in html


def test_alerts_mockup_tabs_and_search_styling() -> None:
    with TestClient(create_app()) as client:
        html = client.get('/').text
        css = client.get('/static/styles.css').text
        assert 'data-alert-tab="all"' in html
        assert 'data-alert-tab="new"' in html
        assert 'data-alert-tab="acknowledged"' in html
        assert 'data-alert-tab="resolved"' in html
        assert 'data-alert-tab="dismissed"' in html
        assert 'Feature 21.1: mockup-aligned alert filters and lifecycle tabs' in css
        assert '.alert-tabs button.active' in css
        assert '.alert-filter-bar .alert-search input' in css
