from pathlib import Path


def test_contract_editor_autogenerates_definition_from_latest_audit():
    html = Path("app/static/index.html").read_text()
    js = Path("app/static/app.js").read_text()

    assert 'id="contractDefinitionStatus"' in html
    assert "populateContractDefinitionFromDataset" in js
    assert "/contract`" in js
    assert "#contractDataset')?.addEventListener('change'" in js
    assert "if(!c)await populateContractDefinitionFromDataset({force:true})" in js


def test_contract_editor_modal_has_rounded_clipped_edges():
    css = Path("app/static/styles.css").read_text()

    assert ".contract-editor-card{" in css
    assert "border-radius:18px" in css
    assert "overflow:hidden" in css
    assert "#contractEditor.modal-shell{overflow:hidden}" in css
