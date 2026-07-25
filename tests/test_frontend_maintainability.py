from pathlib import Path


def test_frontend_modules_are_loaded_in_dependency_order():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    modules = [
        "/static/js/core/http.js",
        "/static/js/core/datetime.js",
        "/static/js/core/dom.js",
        "/static/js/components/feedback.js",
        "/static/js/components/states.js",
        "/static/js/accessibility.js",
        "/static/app.js",
    ]
    positions = [html.rindex(module) if module == "/static/app.js" else html.index(module) for module in modules]
    assert positions == sorted(positions)


def test_accessibility_landmarks_and_live_regions_exist():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert 'class="skip-link" href="#mainContent"' in html
    assert 'id="mainContent"' in html
    assert 'id="appStatusRegion"' in html
    assert 'id="appAlertRegion"' in html


def test_shared_frontend_modules_expose_expected_namespaces():
    http = Path("app/static/js/core/http.js").read_text(encoding="utf-8")
    dates = Path("app/static/js/core/datetime.js").read_text(encoding="utf-8")
    dom = Path("app/static/js/core/dom.js").read_text(encoding="utf-8")
    states = Path("app/static/js/components/states.js").read_text(encoding="utf-8")
    assert "window.DRC.http" in http and "secureFetch" in http
    assert "window.DRC.datetime" in dates and "formatDateTime" in dates
    assert "window.DRC.dom" in dom and "trapDialogFocus" in dom
    assert "window.DRC.states" in states and "shared-empty-state" in states


def test_accessibility_styles_support_focus_and_reduced_motion():
    css = Path("app/static/css/accessibility.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert "forced-colors" in css
