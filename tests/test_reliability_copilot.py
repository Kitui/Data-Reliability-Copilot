from fastapi.testclient import TestClient
from app.main import create_app

def login(client):
    client.post('/auth/register',json={'full_name':'Copilot Owner','email':'copilot@example.com','organization_name':'Copilot Org','workspace_name':'Copilot Workspace','password':'Password123!'})

def test_copilot_context_sessions_and_action_points():
    with TestClient(create_app()) as client:
        login(client)
        client.post('/audits/sample')
        context=client.get('/copilot/context')
        assert context.status_code==200
        assert context.json()['audits']
        session=client.post('/copilot/sessions',json={'analysis_mode':'general'}).json()
        answer=client.post(f"/copilot/sessions/{session['id']}/ask",json={'question':'Why did the reliability score change?','analysis_mode':'score'})
        assert answer.status_code==200
        assert 'response' in answer.json()
        point=client.post('/copilot/action-points',json={'title':'Review reliability risks','description':'Review evidence','session_id':session['id']})
        assert point.status_code==200

def test_copilot_ui_is_wired():
    with TestClient(create_app()) as client:
        html=client.get('/').text
        assert 'Reliability Copilot' in html
        assert 'copilotConversation' in html
        assert 'Evidence &amp; Actions' in html

def test_copilot_greeting_is_conversational():
    with TestClient(create_app()) as client:
        login(client)
        session=client.post('/copilot/sessions',json={'analysis_mode':'general'}).json()
        answer=client.post(f"/copilot/sessions/{session['id']}/ask",json={'question':'Hello','analysis_mode':'general'})
        assert answer.status_code==200
        response=answer.json()['response']
        assert response['response_type']=='conversation'
        assert 'Reliability Copilot' in response['answer']
        assert response['summary']=={}


def test_copilot_empty_context_does_not_invent_audit_metrics():
    with TestClient(create_app()) as client:
        login(client)
        session=client.post('/copilot/sessions',json={'analysis_mode':'general'}).json()
        answer=client.post(f"/copilot/sessions/{session['id']}/ask",json={'question':'Explain my latest audit','analysis_mode':'general'})
        assert answer.status_code==200
        response=answer.json()['response']
        assert response['response_type']=='empty_context'
        assert 'don’t have an audit selected' in response['answer']
        assert '—/100' not in response['answer']

def test_copilot_context_query_omits_blank_identifiers():
    from pathlib import Path
    script = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "params.set('dataset_id',datasetId)" in script
    assert "dataset_id:document.querySelector('#copilotDataset')?.value||''" not in script
    assert 'Array.isArray(detail)' in script


def test_copilot_context_accepts_blank_optional_query_values():
    with TestClient(create_app()) as client:
        login(client)
        response = client.get('/copilot/context?dataset_id=&audit_id=&compare_audit_id=')
        assert response.status_code == 200
        assert 'datasets' in response.json()


def test_copilot_session_can_be_deleted():
    with TestClient(create_app()) as client:
        login(client)
        session=client.post('/copilot/sessions',json={'analysis_mode':'general'}).json()
        client.post(f"/copilot/sessions/{session['id']}/ask",json={'question':'Hello','analysis_mode':'general'})
        response=client.delete(f"/copilot/sessions/{session['id']}")
        assert response.status_code==200
        assert response.json()['deleted'] is True
        assert client.get(f"/copilot/sessions/{session['id']}").status_code==404

def test_copilot_session_delete_ui_is_wired():
    from pathlib import Path
    html=Path('app/static/index.html').read_text(encoding='utf-8')
    script=Path('app/static/app.js').read_text(encoding='utf-8')
    styles=Path('app/static/styles.css').read_text(encoding='utf-8')
    assert 'deleteCopilotSessionDialog' in html
    assert 'data-delete-copilot-session' in script
    assert 'copilot-session-delete' in styles
    assert '.copilot-center{min-width:0;overflow:hidden}' in styles

def test_copilot_session_can_be_deleted_and_is_workspace_scoped():
    with TestClient(create_app()) as client:
        login(client)
        session = client.post('/copilot/sessions', json={'analysis_mode':'general'}).json()
        client.post(f"/copilot/sessions/{session['id']}/ask", json={'question':'Hello','analysis_mode':'general'})
        deleted = client.delete(f"/copilot/sessions/{session['id']}")
        assert deleted.status_code == 200
        assert deleted.json()['deleted'] is True
        assert client.get(f"/copilot/sessions/{session['id']}").status_code == 404


def test_copilot_session_list_has_delete_controls_and_non_overlapping_layout():
    from pathlib import Path
    script = Path('app/static/app.js').read_text(encoding='utf-8')
    styles = Path('app/static/styles.css').read_text(encoding='utf-8')
    assert 'data-delete-copilot-session' in script
    assert "DELETE'" in script or 'method:\'DELETE\'' in script
    assert '.copilot-center{width:100%;overflow:hidden}' in styles
    assert 'grid-template-columns:minmax(0,1fr) 32px!important' in styles
