from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_settings_define_product_identity_and_runtime_paths() -> None:
    settings = get_settings()
    assert settings.app_name == "Data Reliability Copilot"
    assert settings.service_name == "data-reliability-copilot"
    assert settings.audit_dir.exists()
    assert settings.upload_dir.exists()


def test_application_factory_exposes_health_and_dashboard() -> None:
    client = TestClient(create_app())
    health = client.get("/health")
    dashboard = client.get("/")
    assert health.status_code == 200
    assert health.json()["service"] == "data-reliability-copilot"
    assert dashboard.status_code == 200
    assert "Enterprise Reliability Workspace" in dashboard.text


def test_openapi_groups_foundation_routes() -> None:
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Data Reliability Copilot"
    assert "/audits/upload" in schema["paths"]
    assert "/health" in schema["paths"]


def test_feature_pages_use_full_workspace_shell():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert 'id="teamPage"' in html
    assert 'id="teamPanel"' not in html
    assert 'id="auditNavButton"' in html
    assert "Data Sources" not in html


def test_feature_documents_are_kept_in_documents_folder():
    documents = Path("documents")
    assert documents.is_dir()
    assert (documents / "FEATURE_06_FRONTEND_SHELL.md").exists()
    assert not list(Path(".").glob("FEATURE_*.md"))


def test_primary_navigation_uses_page_router():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'data-page-route="datasets"' in html
    assert 'const PAGE_ROUTES' in script
    assert 'datasets: openDatasetsPage' in script
    assert 'event.target.closest("[data-page-route]")' in script


def test_dataset_route_uses_shared_page_router_without_undefined_helper():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "function openDatasetsPage()" in script
    dataset_route = script.split("function openDatasetsPage()", 1)[1].split("function ", 1)[0]
    assert "hideAllPages();" in dataset_route
    assert "hideProductPages" not in script


def test_dataset_import_has_explicit_trigger_and_visible_status():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="datasetImportButton"' in html
    assert 'id="datasetImportStatus"' in html
    assert 'setDatasetImportStatus' in script
    assert 'document.querySelector("#datasetImportInput")?.click()' in script


def test_shared_text_helper_is_available_to_dataset_workspace():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "function setText(selector, value)" in script
    overview = script.split("function renderOverview()", 1)[1].split("bindDashboardShell();", 1)[0]
    assert "const setText=" not in overview
    assert 'setText("#datasetRegisteredMetric"' in script


def test_dataset_registry_uses_metric_icon_and_delete_action():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert "function datasetRegistryIcon()" in script
    assert 'class="dataset-registry-icon"' in script
    assert 'data-delete-dataset' in script
    assert 'method: "DELETE"' in script
    assert "dataset-delete-button" in styles
    assert 'styles.css?v=0.16.20' in html
    assert 'app.js?v=0.16.20' in html


def test_rules_workspace_uses_compact_tabs_and_sample_rule_loader():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="loadSampleRuleButton"' in html
    assert 'class="rules-tabs"' in html
    assert 'border-bottom-color:#5145e5' in css
    assert 'function loadSampleQualityRule()' in js
    assert Path("documents/SAMPLE_QUALITY_RULE.json").is_file()


def test_dataset_labels_render_and_delete_icon_is_explicit():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'id="datasetLabelList"' in html
    assert "function normalizeDatasetLabels" in script
    assert "await selectDataset(optimistic.id)" in script
    assert 'stroke="currentColor"' in script
    assert ".dataset-label-chip .dataset-label-text" in styles
    assert ".dataset-delete-button svg" in styles


def test_dataset_schema_is_wide_and_side_cards_fit_content():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    aside_start = html.index('<aside class="dataset-details-stack">')
    aside_end = html.index('</aside>', aside_start)
    schema_pos = html.index('dataset-schema-wide')
    assert schema_pos > aside_end
    assert '.dataset-schema-wide' in styles
    assert 'grid-column:1;' in styles
    assert '.dataset-details-stack>.dashboard-card' in styles
    assert 'height:auto!important' in styles


def test_dataset_registry_is_fluid_and_has_rows_per_page_controls():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'id="datasetRowsPerPage"' in html
    assert 'id="datasetPreviousPage"' in html
    assert 'id="datasetNextPage"' in html
    assert 'pageSize: 10' in script
    assert 'rows.slice(startIndex, startIndex + datasetState.pageSize)' in script
    assert '.dataset-registry{height:auto!important' in styles


def test_primary_navigation_orders_datasets_before_audit():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert html.index('id="overviewNavButton"') < html.index('id="datasetsNavButton"') < html.index('id="auditNavButton"')


def test_dataset_audit_handoff_and_rerun_are_wired():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'async function handleDatasetAction(action, row)' in script
    assert 'url.searchParams.set("page", "audit")' in script
    assert 'await openAudit(row.latest_audit_id)' in script
    assert "addEventListener('click', rerunSelectedAudit)" in script
    assert "`/audits/${state.audit.audit_id}/rerun`" in script


def test_add_workspace_action_is_visible_and_labeled():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'id="createWorkspaceButton"' in html
    assert 'workspace-add-label">Add workspace<' in html
    assert '.workspace-add-button{width:auto!important' in styles


def test_audit_compare_action_is_visible_and_state_aware():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    javascript = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="auditCompareButton"' in html
    assert 'Compare with Previous Run' in html
    assert 'previousAuditForCurrentV2' in javascript
    assert 'updateAuditCompareActionV2' in javascript
    assert 'button.hidden = false' in javascript


def test_audit_comparison_opens_dedicated_visible_panel():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="auditComparisonPanel"' in html
    assert "auditComparisonPanel" in script
    assert "scrollIntoView" in script
    assert "renderComparisonIssueList" in script


def test_audit_comparison_uses_shared_response_parser():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "const comparison = await parseResponse(response);" in script
    assert "readJsonSafely(response)" not in script


def test_audit_comparison_uses_compact_redesigned_layout():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert "comparison-run-strip" in script
    assert "comparison-score-hero" in script
    assert "Persistent issues" in script
    assert "Column impact changes" in script
    assert ".comparison-detail-grid-v2" in styles


def test_rule_save_flow_verifies_persistence_and_shows_feedback():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="ruleEditorFeedback"' in html
    assert "fetch(`/quality-rules/${saved.id}`)" in script
    assert "Rule created and saved." in script
    assert "Rule created, saved, and assigned." in script

def test_rule_editor_uses_full_height_scroll_region():
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    page = Path("app/static/index.html").read_text(encoding="utf-8")
    assert ".rule-editor-card{\n  display:flex;" in styles
    assert ".rule-editor-card .rule-form-grid{\n  flex:1 1 auto;" in styles
    assert "overflow-y:auto" in styles
    assert "position:static" in styles
    assert "styles.css?v=0.16.20" in page

def test_existing_rule_can_be_assigned_from_editor():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "const assignAfterSave=Boolean(datasetId)&&document.querySelector('#ruleAssignAfterSave').checked;" in script
    assert "syncRuleAssignmentAvailability(true)" in script
    assert "Rule updated, saved, and assigned." in script


def test_feature_17_remediation_applies_deterministic_corrections():
    import pandas as pd
    from app.auditor import audit_dataframe
    from app.remediation import apply_remediation_actions

    frame = pd.DataFrame({"customer_id": ["A", "A", "B"], "status": [" active ", " active ", "INACTIVE"]})
    audit = audit_dataframe(frame, "customers.csv")
    uniqueness = next((issue for issue in audit.issues if issue.category == "uniqueness"), None)
    consistency = next((issue for issue in audit.issues if issue.category == "consistency"), None)
    issue_ids = [issue.id for issue in (uniqueness, consistency) if issue]
    corrected, stats = apply_remediation_actions(frame, audit, issue_ids)
    assert len(corrected) <= len(frame)
    assert stats["removed_rows"] >= 0
    assert isinstance(stats["sample_changes"], list)


def test_feature_17_remediation_preview_schema_supports_score_delta():
    from app.schemas import RemediationPreview

    preview = RemediationPreview(
        audit_id="audit-1", selected_actions=1, rows_before=10, rows_after=9,
        columns_before=3, columns_after=3, score_before=70, projected_score=80,
        projected_score_delta=10, issues_before=3, projected_issues=1,
        changed_cells=2, removed_rows=1, changed_columns=["email"],
        sample_changes=[], warnings=[],
    )
    assert preview.projected_score_delta == 10


def test_remediation_has_dedicated_page_route_and_working_audit_action():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'data-page-route="remediation"' in html
    assert 'id="remediationPageHeader"' in html
    assert 'remediation: openRemediationPage' in script
    assert "navigateToPage('remediation')" in script
    assert 'id="remediationPage"' in html
    assert 'id="tab-remediation" class="tab-panel remediation-standalone-panel"' in html
    assert '["#overviewPage", "#auditPage", "#datasetsPage", "#rulesPage", "#teamPage", "#remediationPage"]' in script
    assert 'animatePage(remediationPage)' in script
    assert '.remediation-page .remediation-standalone-panel { display: block; }' in styles


def test_remediation_uses_in_app_risk_approval_dialog():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="remediationRiskDialog"' in html
    assert 'id="remediationRiskAcknowledgement"' in html
    assert "requestRemediationRiskApproval(preview)" in script
    assert "Projected score will decrease from ${preview.score_before}" not in script


def test_rules_contracts_use_compact_remediation_typography():
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    page = Path("app/static/index.html").read_text(encoding="utf-8")
    assert ".rules-page,.rules-page *{font-weight:400}" in styles
    assert ".rules-page .rules-header h1{font-size:28px" in styles
    assert ".rules-page .rules-metrics strong" in styles
    assert "styles.css?v=0.17.7" in page


def test_sensitive_field_remediation_preserves_email_format_and_uniqueness():
    import pandas as pd
    from app.auditor import audit_dataframe
    from app.remediation import apply_remediation_actions
    from app.privacy import EMAIL_RE

    frame = pd.DataFrame({
        "customer_id": ["C001", "C002", "C003"],
        "email": ["alice@example.com", "bob@example.com", "carol@example.com"],
    })
    audit = audit_dataframe(frame, "customers.csv")
    privacy_issue = next(issue for issue in audit.issues if issue.category == "privacy")
    corrected, stats = apply_remediation_actions(frame, audit, [privacy_issue.id])

    assert corrected["email"].map(lambda value: bool(EMAIL_RE.match(str(value)))).all()
    assert corrected["email"].nunique() == frame["email"].nunique()
    assert not corrected["email"].equals(frame["email"])
    assert any("not a fixed privacy penalty" in warning for warning in stats["warnings"])


def test_sensitive_field_remediation_does_not_use_one_shared_mask_value():
    import pandas as pd
    from app.auditor import audit_dataframe
    from app.remediation import apply_remediation_actions

    frame = pd.DataFrame({"phone_number": ["+254700000001", "+254700000002", "+254700000003"]})
    audit = audit_dataframe(frame, "phones.csv")
    privacy_issue = next(issue for issue in audit.issues if issue.category == "privacy")
    corrected, _ = apply_remediation_actions(frame, audit, [privacy_issue.id])

    assert corrected["phone_number"].nunique() == 3
    assert corrected["phone_number"].str.match(r"^\+254\d{9}$").all()


def test_remediation_apply_persists_generated_audit_and_enables_outputs():
    route = Path("app/api/routes/audits.py").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "persist_rule_executions(corrected_audit.audit_id, corrected_audit.rule_executions)" in route
    assert "state.remediationApplyResult = data" in script
    assert "renderRemediationApplyResult(data)" in script
    assert "exportCleanedCsv" in script
    assert "openCorrectedAudit" in script
    assert 'url.searchParams.set("audit", auditId)' in script
    assert "setRemediationStep(4)" in script


def test_feature_18_dataset_versions_workspace_and_routes_exist():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    route = Path("app/api/routes/datasets.py").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'data-page-route="versions"' in html
    assert 'id="versionsPage"' in html
    assert 'versions: openVersionsPage' in script
    assert 'compareDatasetVersions' in script
    assert '@router.get("/{dataset_id}/versions")' in route
    assert '@router.get("/{dataset_id}/versions/compare")' in route
    assert 'from app.api.dependencies import get_audit_store' in route
    assert 'neutral dataset version history rows' in styles


def test_audit_comparison_tracks_persistent_issues_and_structural_deltas():
    import pandas as pd
    from app.auditor import audit_dataframe
    from app.comparison import compare_audits

    baseline = audit_dataframe(pd.DataFrame({"id": [1, 2, 2], "name": ["A", None, "C"]}), "versions.csv")
    candidate = audit_dataframe(pd.DataFrame({"id": [1, 2], "name": ["A", None], "status": ["ok", "ok"]}), "versions.csv")
    result = compare_audits(baseline, candidate)
    assert result.row_count_delta == -1
    assert result.column_count_delta == 1
    assert "status" in result.schema_changes["added_columns"]
    assert isinstance(result.persistent_issues, list)


def test_feature_18_2_version_compare_feedback_and_neutral_styling():
    app_js = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).resolve().parents[1] / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    index = (Path(__file__).resolve().parents[1] / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert "Comparing the selected versions" in app_js
    assert "Dataset versions compared successfully" in app_js
    assert "const resolvedIssues = Array.isArray" in app_js
    assert "version-snapshot-badge" in app_js
    assert ".version-timeline-row.latest" in styles
    assert "box-shadow: none" in styles
    assert ".versions-page h1" in styles and "font-size: 18px" in styles
    assert "/static/app.js?v=" in index


def test_feature_18_4_compact_pagination_and_accessible_deltas():
    root = Path(__file__).resolve().parents[1] / "app" / "static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    index = (root / "index.html").read_text(encoding="utf-8")
    assert "versionsPerPage: 6" in app_js
    assert "issueMovementsPerPage: 5" in app_js
    assert "versionPrevPage" in index and "versionNextPage" in index
    assert "issueMovementPrev" in index and "issueMovementNext" in index
    assert "version-score-delta" in app_js
    assert ".version-score-delta.positive" in styles
    assert "/static/app.js?v=" in index


def test_feature_19_schema_drift_workspace_is_wired():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    script = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    styles = (root / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    assert 'id="driftNavButton"' in html
    assert 'id="driftPage"' in html
    assert "drift: openDriftPage" in script
    assert "async function loadSchemaDrift" in script
    assert "driftTrendChart" in script and "driftSeverityChart" in script and "driftTypeChart" in script
    assert ".drift-workspace-grid" in styles
    assert '/static/app.js?v=' in html


def test_feature_19_schema_drift_router_is_registered():
    main = Path("app/main.py").read_text(encoding="utf-8")
    route = Path("app/api/routes/schema_drift.py").read_text(encoding="utf-8")
    assert "application.include_router(schema_drift.router)" in main
    assert 'APIRouter(prefix="/schema-drift"' in route
    assert 'def list_schema_drift' in route
    assert 'def export_schema_drift' in route


def test_version_import_confirmation_uses_defined_date_formatter():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "formatDate(body.audit_created_at)" not in script
    assert "new Date(body.audit_created_at).toLocaleString()" in script


def test_version_import_result_navigation_uses_valid_routes_and_context():
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'versionWorkspaceState.pendingDatasetId = Number(body.dataset_id)' in script
    assert 'driftState.pendingDatasetId = Number(body.dataset_id)' in script
    assert 'navigateToPage("versions")' in script
    assert 'navigateToPage("drift")' in script
    assert 'navigateToPage("schema-drift")' not in script
    assert 'versionsState.datasetId' not in script

def test_feature_20_scheduled_audits_assets_are_wired():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="schedulesPage"' in html
    assert 'id="schedulesNavButton"' in html
    assert 'id="newScheduleButton"' in html
    assert 'schedules: openSchedulesPage' in js
    assert "fetch('/schedules')" in js


def test_feature_20_navigation_is_grouped_and_workspace_selector_is_in_sidebar():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert 'nav-group-label">Data management<' in html
    assert 'nav-group-label">Automation<' in html
    assert 'nav-group-label">Governance<' in html
    assert 'nav-group-label">Administration<' in html
    assert 'class="sidebar-workspace"' in html


def test_scheduled_audit_score_is_persisted_as_numeric_and_empty_form_error_is_hidden() -> None:
    schedules = (Path(__file__).parents[1] / "app" / "api" / "routes" / "schedules.py").read_text(encoding="utf-8")
    handlers = (Path(__file__).parents[1] / "app" / "jobs" / "handlers.py").read_text(encoding="utf-8")
    html = (Path(__file__).parents[1] / "app" / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (Path(__file__).parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "run.score = result.score.overall" in handlers
    assert '"score": result.score.overall' in handlers
    assert 'id="scheduleFormError" class="form-error hidden"' in html
    assert "error.classList.add('hidden')" in javascript
    assert "error.classList.remove('hidden')" in javascript


def test_feature_20_3_schedule_controls_calendar_and_delete_dialog_are_wired() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "static"
    html = (root / "index.html").read_text(encoding="utf-8")
    javascript = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    assert 'id="scheduleCalendarDialog"' in html
    assert 'id="deleteScheduleDialog"' in html
    assert "viewScheduleCalendar')?.addEventListener('click',openScheduleCalendar" in javascript
    assert "confirm('Delete this audit schedule?')" not in javascript
    assert "confirmDeleteSchedule" in javascript
    assert '.schedule-actions button[type="button"]' in styles
    assert '/static/app.js?v=' in html


def test_feature_20_4_month_calendar_polished_table_and_worker_are_wired() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    styles = (root / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    schedules = (root / "app" / "api" / "routes" / "schedules.py").read_text(encoding="utf-8")
    assert 'id="scheduleCalendarPrevious"' in html
    assert 'id="scheduleCalendarNext"' in html
    assert 'class="schedule-calendar-weekdays"' in html
    assert "scheduleOccurrencesForMonth" in javascript
    assert "showScheduleCalendarTooltip" in javascript
    assert "scheduleIcons" in javascript
    assert ".calendar-day.has-runs" in styles
    assert ".schedule-cell-stack" in styles
    assert "_scheduled_audit_worker" not in main
    assert "asyncio.to_thread(schedules.process_all_due)" not in main
    assert "def process_all_due" in schedules
    assert '@router.post("/dispatch"' in schedules
    assert '/static/app.js?v=' in html


def test_collapsible_navigation_shell_and_workspace_footer_are_wired():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="sidebarToggleButton"' in html
    assert 'class="nav-group-toggle"' in html
    assert 'data-nav-group="ai-assistance"' in html
    assert 'class="sidebar-footer"' in html
    assert 'class="nav-new"' not in html
    assert 'body.sidebar-collapsed .nav-group:hover>.nav-group-items' in css
    assert 'position:sticky' in css
    assert 'drc-sidebar-collapsed' in js


def test_final_ui_consistency_review_is_wired() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    styles = (root / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    assert '/static/styles.css?v=0.25.0' in html
    assert '/static/app.js?v=' in html
    assert 'id="appMessageDialog"' in html
    assert 'aria-live="polite"' in html
    assert "confirmAppAction" in javascript
    assert "showAppMessage" in javascript
    assert "window.confirm(" not in javascript
    assert "=>alert(" not in javascript
    assert "applyConsistentShellIcons" in javascript
    assert ".ui-loading-state" in styles
    assert ":focus-visible" in styles
    assert "prefers-reduced-motion" in styles
