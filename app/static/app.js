// Core utilities are loaded from /static/js/core modules.
const readCookie = window.DRC.http.readCookie;
const DISPLAY_TIME_ZONE = "Africa/Nairobi";
const parseServerDate = window.DRC.datetime.parseServerDate;
const formatDateTime = window.DRC.datetime.formatDateTime;

const authEls = {
  gate: document.querySelector("#authGate"), loginForm: document.querySelector("#loginForm"), registerForm: document.querySelector("#registerForm"),
  email: document.querySelector("#loginEmail"), password: document.querySelector("#loginPassword"),
  error: document.querySelector("#loginError"), registerName: document.querySelector("#registerName"), registerEmail: document.querySelector("#registerEmail"), registerOrganization: document.querySelector("#registerOrganization"), registerWorkspace: document.querySelector("#registerWorkspace"), registerPassword: document.querySelector("#registerPassword"), registerConfirmPassword: document.querySelector("#registerConfirmPassword"), registerError: document.querySelector("#registerError"), showRegisterButton: document.querySelector("#showRegisterButton"), showLoginButton: document.querySelector("#showLoginButton"), inviteAcceptForm: document.querySelector("#inviteAcceptForm"),
  invitePassword: document.querySelector("#invitePassword"), inviteAcceptError: document.querySelector("#inviteAcceptError"), inviteAcceptMessage: document.querySelector("#inviteAcceptMessage"), profileButton: document.querySelector("#profileButton"),
  profileMenu: document.querySelector("#profileMenu"), profileName: document.querySelector("#profileName"),
  profileEmail: document.querySelector("#profileEmail"), profileRole: document.querySelector("#profileRole"),
  logoutButton: document.querySelector("#logoutButton"), workspaceSelect: document.querySelector("#workspaceSelect"), createWorkspaceButton: document.querySelector("#createWorkspaceButton"), workspaceDialog: document.querySelector("#workspaceDialog"), workspaceCreateForm: document.querySelector("#workspaceCreateForm"), newWorkspaceName: document.querySelector("#newWorkspaceName"), newWorkspaceDescription: document.querySelector("#newWorkspaceDescription"), workspaceCreateError: document.querySelector("#workspaceCreateError"), closeWorkspaceDialog: document.querySelector("#closeWorkspaceDialog"), cancelWorkspaceCreate: document.querySelector("#cancelWorkspaceCreate"),
  organizationName: document.querySelector("#organizationName"),
  manageTeamButton: document.querySelector("#manageTeamButton"), overviewNavButton: document.querySelector("#overviewNavButton"), auditNavButton: document.querySelector("#auditNavButton"), datasetsNavButton: document.querySelector("#datasetsNavButton"), teamNavButton: document.querySelector("#teamNavButton"), rulesNavButton: document.querySelector("#rulesNavButton"), remediationNavButton: document.querySelector("#remediationNavButton"),
  teamPage: document.querySelector("#teamPage"),
  inviteForm: document.querySelector("#inviteForm"), inviteName: document.querySelector("#inviteName"),
  inviteEmail: document.querySelector("#inviteEmail"), inviteRole: document.querySelector("#inviteRole"),
  inviteResult: document.querySelector("#inviteResult"), teamMembers: document.querySelector("#teamMembers"),
  teamInvitations: document.querySelector("#teamInvitations"), teamPermissionNote: document.querySelector("#teamPermissionNote"),
  refreshTeamButton: document.querySelector("#refreshTeamButton"),
};

function bindAuthentication() {
  authEls.loginForm.addEventListener("submit", login);
  authEls.registerForm.addEventListener("submit", registerAccount);
  authEls.showRegisterButton.addEventListener("click", () => showAuthForm("register"));
  authEls.showLoginButton.addEventListener("click", () => showAuthForm("login"));
  authEls.inviteAcceptForm.addEventListener("submit", acceptInvitation);
  authEls.logoutButton.addEventListener("click", logout);
  authEls.profileButton.addEventListener("click", () => authEls.profileMenu.classList.toggle("hidden"));
  authEls.workspaceSelect.addEventListener("change", switchWorkspace);
  authEls.createWorkspaceButton.addEventListener("click", openWorkspaceDialog);
  authEls.closeWorkspaceDialog.addEventListener("click", closeWorkspaceDialog);
  authEls.cancelWorkspaceCreate.addEventListener("click", closeWorkspaceDialog);
  authEls.workspaceDialog.addEventListener("click", (event) => { if (event.target.matches("[data-close-workspace-dialog]")) closeWorkspaceDialog(); });
  authEls.workspaceCreateForm.addEventListener("submit", createWorkspace);
  authEls.manageTeamButton.addEventListener("click", openTeamPage);
  authEls.rulesNavButton.addEventListener("click", () => navigateToPage("rules"));
  authEls.refreshTeamButton.addEventListener("click", loadTeam);
  authEls.inviteForm.addEventListener("submit", createInvitation);
}

const PAGE_ROUTES = {
  overview: openOverviewPage,
  audit: openAuditPage,
  datasets: openDatasetsPage,
  rules: openRulesPage,
  remediation: openRemediationPage,
  versions: openVersionsPage,
  drift: openDriftPage,
  schedules: openSchedulesPage,
  alerts: openAlertsPage,
  connectors: openConnectorsPage,
  copilot: openCopilotPage,
  reports: openReportsPage,
  team: openTeamPage,
};

function bindPageRouter() {
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-page-route]");
    if (!trigger) return;
    event.preventDefault();
    navigateToPage(trigger.dataset.pageRoute);
  });
  window.addEventListener("popstate", () => {
    const route = new URL(window.location.href).searchParams.get("page") || "overview";
    showPageRoute(route, false);
  });
}

function navigateToPage(route) {
  showPageRoute(route, true);
}

function showPageRoute(route, updateHistory = false) {
  const safeRoute = PAGE_ROUTES[route] ? route : "overview";
  PAGE_ROUTES[safeRoute]();
  if (updateHistory) {
    const url = new URL(window.location.href);
    if (safeRoute === "overview") url.searchParams.delete("page");
    else url.searchParams.set("page", safeRoute);
    history.pushState({ page: safeRoute }, "", url);
  }
}

async function initializeSession() {
  const inviteToken = new URLSearchParams(window.location.search).get("invite");
  if (inviteToken) { authEls.gate.classList.remove("hidden"); authEls.loginForm.classList.add("hidden"); authEls.inviteAcceptForm.classList.remove("hidden"); return; }
  const response = await fetch("/auth/me");
  if (!response.ok) { authEls.gate.classList.remove("hidden"); return; }
  const payload = await response.json();
  showAuthenticatedUser(payload.user);
  await loadWorkspaces(payload.user);
  await loadHistory();
  const requestedPage = new URL(window.location.href).searchParams.get("page") || "overview";
  showPageRoute(requestedPage, false);
}


async function acceptInvitation(event) {
  event.preventDefault();
  const token = new URLSearchParams(window.location.search).get("invite");
  authEls.inviteAcceptError.textContent = "";
  const response = await fetch("/team/invitations/accept", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({token,password:authEls.invitePassword.value})});
  const payload = await response.json().catch(()=>({}));
  if (!response.ok) { authEls.inviteAcceptError.textContent = payload.detail || "Unable to accept invitation."; return; }
  authEls.inviteAcceptMessage.textContent = payload.message;
  authEls.invitePassword.value = "";
  history.replaceState({}, "", window.location.pathname);
  setTimeout(() => { authEls.inviteAcceptForm.classList.add("hidden"); authEls.loginForm.classList.remove("hidden"); }, 800);
}

function showAuthForm(mode) {
  authEls.loginForm.classList.toggle("hidden", mode !== "login");
  authEls.registerForm.classList.toggle("hidden", mode !== "register");
  authEls.inviteAcceptForm.classList.add("hidden");
  authEls.error.textContent = "";
  authEls.registerError.textContent = "";
}

async function registerAccount(event) {
  event.preventDefault();
  authEls.registerError.textContent = "";
  if (authEls.registerPassword.value !== authEls.registerConfirmPassword.value) {
    authEls.registerError.textContent = "Passwords do not match.";
    return;
  }
  const response = await fetch("/auth/register", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      full_name: authEls.registerName.value, email: authEls.registerEmail.value,
      organization_name: authEls.registerOrganization.value, workspace_name: authEls.registerWorkspace.value,
      password: authEls.registerPassword.value,
    }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) { authEls.registerError.textContent = payload.detail || "Account creation failed."; return; }
  authEls.registerPassword.value = ""; authEls.registerConfirmPassword.value = "";
  showAuthenticatedUser(payload.user); await loadWorkspaces(payload.user); await loadHistory(); openOverviewPage();
}

async function login(event) {
  event.preventDefault(); authEls.error.textContent = "";
  const response = await fetch("/auth/login", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:authEls.email.value, password:authEls.password.value})});
  if (!response.ok) { const body = await response.json().catch(()=>({})); authEls.error.textContent = body.detail || "Sign-in failed."; return; }
  const payload = await response.json(); authEls.password.value = ""; showAuthenticatedUser(payload.user); await loadWorkspaces(payload.user); await loadHistory();
}

function showAuthenticatedUser(user) {
  authEls.gate.classList.add("hidden"); authEls.profileMenu.classList.add("hidden");
  authEls.profileName.textContent = user.full_name; authEls.profileEmail.textContent = user.email; authEls.profileRole.textContent = user.role;
  const initials = user.full_name.split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase();
  const avatar = authEls.profileButton.querySelector(".profile-avatar"); if (avatar) avatar.textContent = initials;
  const topName = document.querySelector("#topProfileName"); if (topName) topName.textContent = user.full_name;
  const topRole = document.querySelector("#topProfileRole"); if (topRole) topRole.textContent = user.role || user.membership_role || "Member";
  authEls.organizationName.textContent = user.organization?.name || "No organization";
  state.currentUser = user;
  const role = user.membership_role || user.role;
  authEls.createWorkspaceButton.classList.toggle("hidden", !["owner", "admin"].includes(String(role || "").toLowerCase()));
}

async function loadWorkspaces(user) {
  const response = await fetch("/workspaces");
  if (!response.ok) return;
  const workspaces = await response.json();
  authEls.workspaceSelect.innerHTML = workspaces.map(w => `<option value="${w.id}" ${w.active ? "selected" : ""}>${escapeHtml(w.name)}</option>`).join("");
  const role = user?.membership_role || user?.role || state.currentUser?.membership_role || state.currentUser?.role;
  authEls.createWorkspaceButton.classList.toggle("hidden", !["owner", "admin"].includes(String(role || "").toLowerCase()));
}

function openWorkspaceDialog() {
  authEls.workspaceCreateError.textContent = "";
  authEls.workspaceCreateForm.reset();
  authEls.workspaceDialog.classList.remove("hidden");
  requestAnimationFrame(() => authEls.newWorkspaceName.focus());
}

function closeWorkspaceDialog() {
  authEls.workspaceDialog.classList.add("hidden");
  authEls.workspaceCreateError.textContent = "";
}

async function createWorkspace(event) {
  event.preventDefault();
  authEls.workspaceCreateError.textContent = "";
  const submitButton = document.querySelector("#submitWorkspaceCreate");
  submitButton.disabled = true;
  submitButton.textContent = "Creating\u2026";
  try {
    const response = await fetch("/workspaces", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        name: authEls.newWorkspaceName.value.trim(),
        description: authEls.newWorkspaceDescription.value.trim() || null,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      authEls.workspaceCreateError.textContent = payload.detail || "Unable to create workspace.";
      return;
    }
    const activate = await fetch(`/workspaces/${payload.id}/activate`, {method: "POST"});
    if (!activate.ok) {
      authEls.workspaceCreateError.textContent = "Workspace was created but could not be activated.";
      return;
    }
    await loadWorkspaces(state.currentUser);
    closeWorkspaceDialog();
    state.audit = null; state.history = [];
    await loadHistory();
    openOverviewPage();
    setStatus(`${payload.name} workspace created and activated.`);
  } catch (error) {
    authEls.workspaceCreateError.textContent = "Unable to create workspace. Check the connection and try again.";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Create and activate";
  }
}

function clearWorkspaceScopedState() {
  state.audit = null;
  state.history = [];
  state.remediation = null;
  state.contract = null;
  state.selectedIssueId = null;
  state.selectedColumn = null;
  state.selectedIssueIds.clear();
  state.selectedActionIds.clear();
  state.chat = [];

  document.querySelector("#workbench")?.classList.add("hidden");
  document.querySelector("#emptyState")?.classList.remove("hidden");
  if (auditV2.dashboard) auditV2.dashboard.classList.add("hidden");
  if (auditV2.empty) auditV2.empty.classList.remove("hidden");
  if (auditV2.dataset) auditV2.dataset.innerHTML = '<option value="">No datasets in this workspace</option>';
  if (auditV2.run) auditV2.run.innerHTML = '<option value="">No audit runs</option>';
  document.querySelector("#auditComparisonPanel")?.classList.add("hidden");
}

function clearWorkspaceAuditUrl() {
  const url = new URL(window.location.href);
  ["audit", "dataset", "dataset_name", "tab"].forEach((key) => url.searchParams.delete(key));
  if (url.searchParams.get("page") === "audit") url.searchParams.set("page", "overview");
  window.history.replaceState({}, "", url);
}

async function switchWorkspace() {
  const response = await fetch(`/workspaces/${authEls.workspaceSelect.value}/activate`, {method:"POST"});
  if (!response.ok) { setStatus("Unable to switch workspace."); return; }
  clearWorkspaceScopedState();
  clearWorkspaceAuditUrl();
  openOverviewPage();
  await loadHistory();
  setStatus("Workspace switched. Workspace-specific audit context was cleared.");
}

async function logout() {
  await fetch("/auth/logout", {method:"POST"}); authEls.profileMenu.classList.add("hidden"); authEls.gate.classList.remove("hidden"); showAuthForm("login");
}

const state = {
  audit: null,
  history: [],
  remediation: null,
  remediationPreview: null,
  remediationApplyResult: null,
  contract: null,
  selectedIssueId: null,
  selectedColumn: null,
  selectedIssueIds: new Set(),
  selectedActionIds: new Set(),
  filters: { category: "all", severity: "all", status: "all", search: "" },
  chat: [],
  busy: false,
  currentUser: null,
};

const els = {
  fileInput: document.querySelector("#fileInput"),
  uploadButton: document.querySelector("#uploadButton"),
  sampleButton: document.querySelector("#sampleButton"),
  emptySampleButton: document.querySelector("#emptySampleButton"),
  emptyRulesButton: document.querySelector("#emptyRulesButton"),
  refreshHistoryButton: document.querySelector("#refreshHistoryButton"),
  regenerateButton: document.querySelector("#regenerateButton"),
  loadRemediationButton: document.querySelector("#loadRemediationButton"),
  loadContractButton: document.querySelector("#loadContractButton"),
  useContractButton: document.querySelector("#useContractButton"),
  copyScriptButton: document.querySelector("#copyScriptButton"),
  previewRemediationButton: document.querySelector("#previewRemediationButton"),
  applyRemediationButton: document.querySelector("#applyRemediationButton"),
  remediationRiskDialog: document.querySelector("#remediationRiskDialog"),
  remediationRiskAcknowledgement: document.querySelector("#remediationRiskAcknowledgement"),
  confirmRemediationRiskDialog: document.querySelector("#confirmRemediationRiskDialog"),
  compareButton: document.querySelector("#compareButton"),
  askAnalystButton: document.querySelector("#askAnalystButton"),
  syncRulesButton: document.querySelector("#syncRulesButton"),
  statusText: document.querySelector("#status"),
  emptyState: document.querySelector("#emptyState"),
  workbench: document.querySelector("#workbench"),
  severityFilter: document.querySelector("#severityFilter"),
  categoryFilter: document.querySelector("#categoryFilter"),
  statusFilter: document.querySelector("#statusFilter"),
  issueSearch: document.querySelector("#issueSearch"),
  selectAllIssues: document.querySelector("#selectAllIssues"),
  baselineSelect: document.querySelector("#baselineSelect"),
  analystQuestion: document.querySelector("#analystQuestion"),
  rulesInput: document.querySelector("#rulesInput"),
  reportLink: document.querySelector("#reportLink"),
  nextAction: document.querySelector("#nextAction"),
  qualityPosture: document.querySelector("#qualityPosture"),
  protectedFields: document.querySelector("#protectedFields"),
};

bindEvents();
bindAuthentication();
bindPageRouter();
renderPromptChips();
initializeSession();

function bindEvents() {
  els.uploadButton.addEventListener("click", uploadCsv);
  els.fileInput.addEventListener("change", () => {
    if (!els.fileInput.files.length) return;
    const file = els.fileInput.files[0];
    setStatus(`Selected ${file.name}. Starting audit...`);
    uploadCsv();
  });
  els.sampleButton.addEventListener("click", () => runAudit("/audits/sample", { method: "POST" }));
  els.emptySampleButton.addEventListener("click", () => runAudit("/audits/sample", { method: "POST" }));
  els.emptyRulesButton.addEventListener("click", () => activateTab("rules"));
  els.refreshHistoryButton.addEventListener("click", loadHistory);
  els.regenerateButton.addEventListener("click", regenerateSummary);
  els.loadRemediationButton.addEventListener("click", loadRemediation);
  els.loadContractButton.addEventListener("click", loadContract);
  els.useContractButton.addEventListener("click", useContractAsRules);
  els.copyScriptButton.addEventListener("click", copySelectedScript);
  els.previewRemediationButton?.addEventListener("click", previewRemediation);
  els.applyRemediationButton?.addEventListener("click", applyRemediation);
  document.querySelector("#remediationExportPlaceholder")?.addEventListener("click", exportCleanedCsv);
  document.querySelector("#closeRemediationRiskDialog")?.addEventListener("click", () => resolveRemediationRiskDialog(false));
  document.querySelector("#cancelRemediationRiskDialog")?.addEventListener("click", () => resolveRemediationRiskDialog(false));
  els.confirmRemediationRiskDialog?.addEventListener("click", () => resolveRemediationRiskDialog(true));
  els.remediationRiskAcknowledgement?.addEventListener("change", () => {
    els.confirmRemediationRiskDialog.disabled = !els.remediationRiskAcknowledgement.checked;
  });
  els.remediationRiskDialog?.addEventListener("click", (event) => {
    if (event.target === els.remediationRiskDialog) resolveRemediationRiskDialog(false);
  });
  els.compareButton.addEventListener("click", compareAudits);
  els.askAnalystButton.addEventListener("click", askAnalyst);
  els.syncRulesButton.addEventListener("click", syncRulesFromBuilder);
  els.selectAllIssues.addEventListener("change", toggleAllIssues);

  els.issueSearch.addEventListener("input", () => {
    state.filters.search = els.issueSearch.value.trim().toLowerCase();
    renderIssues();
  });
  els.severityFilter.addEventListener("change", () => {
    state.filters.severity = els.severityFilter.value;
    renderIssues();
  });
  els.categoryFilter.addEventListener("change", () => {
    state.filters.category = els.categoryFilter.value;
    renderIssues();
  });
  els.statusFilter.addEventListener("change", () => {
    state.filters.status = els.statusFilter.value;
    renderIssues();
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
  document.querySelectorAll("[data-score-filter]").forEach((card) => {
    card.addEventListener("click", () => applyScoreFilter(card.dataset.scoreFilter));
  });
  document.querySelectorAll("[data-bulk-status]").forEach((button) => {
    button.addEventListener("click", () => bulkUpdateStatus(button.dataset.bulkStatus));
  });
  document.querySelectorAll("[data-rule-mode]").forEach((button) => {
    button.addEventListener("click", () => switchRuleMode(button.dataset.ruleMode));
  });
}

async function uploadCsv() {
  if (!els.fileInput.files.length) {
    setStatus("Choose a CSV file first.");
    return;
  }
  if (state.busy) return;
  const file = els.fileInput.files[0];
  if (!file.name.toLowerCase().endsWith(".csv") || !["text/csv","application/vnd.ms-excel",""] .includes(file.type)) {
    setStatus("Please upload a CSV file. This MVP does not read Excel files yet.");
    return;
  }
  syncRulesFromBuilder(false);
  const form = new FormData();
  form.append("file", file);
  if (els.rulesInput.value.trim()) form.append("rules_json", els.rulesInput.value.trim());
  await runBackgroundAudit(form, file.name);
}

async function runBackgroundAudit(form, filename) {
  setBusy(true);
  setStatus(`Uploading ${filename} and creating background job...`);
  try {
    const response = await fetch("/audits/upload/async", { method: "POST", body: form });
    const job = await parseResponse(response);
    if (!response.ok) throw new Error(responseErrorMessage(job, response.status));
    setStatus(`Audit queued. Job #${job.id} is ${job.status}.`);
    const result = await pollBackgroundJob(job.id);
    if (!result?.audit_id) throw new Error("The audit job completed without an audit result.");
    await openAudit(result.audit_id);
    await loadHistory();
    setStatus(`Completed background audit for ${result.dataset_name}.`);
    document.querySelector("#workbench")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return result;
  } catch (error) {
    setStatus(error.message || "Background audit failed.");
    return null;
  } finally {
    setBusy(false);
  }
}

async function pollBackgroundJob(jobId) {
  const terminal = new Set(["completed", "failed", "cancelled"]);
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 800));
    const response = await fetch(`/jobs/${jobId}`);
    const job = await parseResponse(response);
    if (!response.ok) throw new Error(responseErrorMessage(job, response.status));
    setStatus(`Audit job #${job.id}: ${job.status.replaceAll("_", " ")} (${job.progress}%).`);
    if (!terminal.has(job.status)) continue;
    if (job.status === "completed") return job.result;
    throw new Error(job.error_message || `Audit job ${job.status}.`);
  }
}

async function runAudit(url, options, busyMessage = "Auditing...") {
  setBusy(true);
  setStatus(busyMessage);
  try {
    const response = await fetch(url, options);
    const payload = await parseResponse(response);
    if (!response.ok) throw new Error(responseErrorMessage(payload, response.status));
    renderAudit(payload);
    try {
      await loadHistory();
    } catch (historyError) {
      console.warn(historyError);
      setStatus(`Completed audit for ${payload.dataset_name}. History refresh failed.`);
      return payload;
    }
    setStatus(`Completed audit for ${payload.dataset_name}`);
    document.querySelector("#workbench")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return payload;
  } catch (error) {
    setStatus(error.message || "Audit failed. Please try another CSV.");
    return null;
  } finally {
    setBusy(false);
  }
}

async function parseResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function responseErrorMessage(payload, status) {
  if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || JSON.stringify(item)).join(" ");
  if (status === 413) return "That CSV is too large for this deployment. Try a smaller file or increase the Render upload limit.";
  if (status >= 500) return "The server hit an error while auditing this CSV. Check the Render logs for the exact traceback.";
  return "Audit failed. Confirm the file is a valid CSV and try again.";
}

async function loadHistory() {
  const response = await fetch("/audits");
  state.history = await response.json();
  renderHistory();
  renderOverview();
  renderCompareOptions();
  populateAuditSelectorsV2();
  updateAuditCompareActionV2();
}

function renderHistory() {
  const history = document.querySelector("#history");
  history.innerHTML = "";
  if (!state.history.length) {
    history.innerHTML = '<p class="empty">No saved audits yet.</p>';
    return;
  }
  state.history.forEach((audit) => {
    const button = document.createElement("button");
    button.className = `history-item ${state.audit?.audit_id === audit.audit_id ? "active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(audit.dataset_name)}</strong>
      <span>${audit.score}/100 - ${escapeHtml(audit.risk_level)} - ${audit.issue_count} issues</span>
      <span>${new Date(audit.created_at).toLocaleString()}</span>
    `;
    button.addEventListener("click", () => openAudit(audit.audit_id));
    history.appendChild(button);
  });
}

async function openAudit(auditId) {
  setStatus("Loading saved audit...");
  const response = await fetch(`/audits/${auditId}`);
  const payload = await parseResponse(response);
  if (!response.ok) {
    clearWorkspaceScopedState();
    const url = new URL(window.location.href);
    url.searchParams.delete("audit");
    window.history.replaceState({}, "", url);
    const message = response.status === 404
      ? "That audit is not available in the active workspace."
      : responseErrorMessage(payload, response.status);
    setStatus(message);
    throw new Error(message);
  }
  renderAudit(payload);
  setStatus("Saved audit loaded.");
  return payload;
}

function renderAudit(audit) {
  state.audit = audit;
  state.remediation = null;
  state.contract = null;
  state.selectedIssueId = audit.issues[0]?.id || null;
  state.selectedColumn = null;
  state.selectedIssueIds.clear();
  state.selectedActionIds.clear();
  state.chat = [];
  els.emptyState.classList.add("hidden");
  els.workbench.classList.remove("hidden");
  els.reportLink.classList.remove("hidden");
  els.reportLink.href = `/audits/${audit.audit_id}/report.html`;

  document.querySelector("#currentDataset").textContent = audit.dataset_name;
  document.querySelector("#currentTitle").textContent = `${audit.score.overall}/100 quality score - ${audit.summary.risk_level} risk`;
  document.body.dataset.risk = audit.summary.risk_level;
  document.querySelector("#score").textContent = audit.score.overall;
  document.querySelector("#risk").textContent = audit.summary.risk_level;
  document.querySelector("#summarySource").textContent = audit.summary.source;
  document.querySelector("#summaryText").textContent = audit.summary.executive_summary;
  document.querySelector("#privacyCount").textContent = privacyColumns(audit).length;
  document.querySelector("#scoreCompleteness").textContent = audit.score.completeness;
  document.querySelector("#scoreValidity").textContent = audit.score.validity;
  document.querySelector("#scoreUniqueness").textContent = audit.score.uniqueness;
  setMeter("#meterCompleteness", audit.score.completeness);
  setMeter("#meterValidity", audit.score.validity);
  setMeter("#meterUniqueness", audit.score.uniqueness);

  renderList("#focusList", audit.summary.recommended_focus);
  renderList("#remediationList", audit.summary.remediation_plan);
  renderSignalStrip(audit);
  renderBreakdown(audit.score);
  renderFilters(audit.issues);
  renderIssues();
  renderColumns();
  renderInspector();
  renderCompareOptions();
  renderContractMini();
  renderChat();
  renderHistory();
  renderAuditWorkspaceV2(audit);
}

function renderSignalStrip(audit) {
  const topIssue = audit.issues[0];
  els.nextAction.textContent = topIssue ? `${topIssue.id}: ${topIssue.title}` : "Keep monitoring new uploads";
  els.qualityPosture.textContent = `${audit.summary.risk_level} risk - ${audit.score.overall}/100 score`;
  const fields = privacyColumns(audit);
  els.protectedFields.textContent = fields.length ? fields.join(", ") : "None flagged";
}

function renderBreakdown(score) {
  const items = [
    ["Completeness", score.completeness, "completeness"],
    ["Validity", score.validity, "validity"],
    ["Consistency", score.consistency, "consistency"],
    ["Uniqueness", score.uniqueness, "uniqueness"],
    ["Reliability", score.reliability, "all"],
  ];
  document.querySelector("#scoreBreakdown").innerHTML = items.map(([label, value, filter]) => `
    <button class="dimension-card" data-dimension-filter="${filter}">
      <span>${label}</span>
      <strong>${value}</strong>
      <div class="meter"><i style="width:${value}%"></i></div>
    </button>
  `).join("");
  document.querySelectorAll("[data-dimension-filter]").forEach((button) => {
    button.addEventListener("click", () => applyScoreFilter(button.dataset.dimensionFilter));
  });
}

function renderFilters(issues) {
  fillSelect(els.severityFilter, "All severities", [...new Set(issues.map((issue) => issue.severity))]);
  fillSelect(els.categoryFilter, "All categories", [...new Set(issues.map((issue) => issue.category))]);
  fillSelect(els.statusFilter, "All statuses", [...new Set(issues.map((issue) => issue.status || "open"))]);
}

function filteredIssues() {
  if (!state.audit) return [];
  return state.audit.issues.filter((issue) => {
    const query = `${issue.title} ${issue.detail} ${issue.recommendation} ${issue.columns.join(" ")}`.toLowerCase();
    return (
      (state.filters.severity === "all" || issue.severity === state.filters.severity) &&
      (state.filters.category === "all" || issue.category === state.filters.category) &&
      (state.filters.status === "all" || (issue.status || "open") === state.filters.status) &&
      (!state.filters.search || query.includes(state.filters.search))
    );
  });
}

function renderIssues() {
  if (!state.audit) return;
  const issues = filteredIssues();
  const body = document.querySelector("#issueTableBody");
  body.innerHTML = issues.length ? "" : '<tr><td colspan="7" class="empty-cell">No issues match the current filters.</td></tr>';
  issues.forEach((issue) => {
    const row = document.createElement("tr");
    row.className = state.selectedIssueId === issue.id ? "selected" : "";
    row.innerHTML = `
      <td><input type="checkbox" data-select-issue="${escapeHtml(issue.id)}" ${state.selectedIssueIds.has(issue.id) ? "checked" : ""}></td>
      <td><button class="table-link" data-open-issue="${escapeHtml(issue.id)}">${escapeHtml(issue.title)}<small>${escapeHtml(issue.columns.join(", "))}</small></button></td>
      <td><span class="badge severity-${escapeHtml(issue.severity)}">${escapeHtml(issue.severity)}</span></td>
      <td><span class="badge">${escapeHtml(issue.category)}</span></td>
      <td><select data-issue-status="${escapeHtml(issue.id)}">${statusOptions(issue.status || "open")}</select></td>
      <td>${issue.affected_rows}</td>
      <td>${Math.round(issue.confidence * 100)}%</td>
    `;
    body.appendChild(row);
  });

  document.querySelector("#issueCount").textContent = `${filteredIssues().length}/${state.audit.issues.length}`;
  document.querySelector("#selectionCount").textContent = `${state.selectedIssueIds.size} selected`;

  document.querySelectorAll("[data-open-issue]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedIssueId = button.dataset.openIssue;
      state.selectedColumn = null;
      renderIssues();
      renderInspector();
    });
  });
  document.querySelectorAll("[data-select-issue]").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) state.selectedIssueIds.add(box.dataset.selectIssue);
      else state.selectedIssueIds.delete(box.dataset.selectIssue);
      renderIssues();
    });
  });
  document.querySelectorAll("[data-issue-status]").forEach((select) => {
    select.addEventListener("change", () => updateIssueStatus(select.dataset.issueStatus, select.value));
  });
}

function renderColumns() {
  const grid = document.querySelector("#columnGrid");
  grid.innerHTML = "";
  state.audit.profile.columns.forEach((column) => {
    const related = state.audit.issues.filter((issue) => issue.columns.includes(column.name));
    const missingPct = Math.round(column.missing_rate * 100);
    const uniquePct = Math.round(column.unique_rate * 100);
    const missingCount = column.missing_count || 0;
    const health = columnHealth(column, related);
    const card = document.createElement("article");
    card.className = `column-card ${state.selectedColumn === column.name ? "selected" : ""}`;
    card.innerHTML = `
      <button class="column-main" data-open-column="${escapeHtml(column.name)}">
        <span>
          <strong>${escapeHtml(column.name)}</strong>
          <small>${escapeHtml(column.inferred_type)} - ${related.length} signal${related.length === 1 ? "" : "s"}</small>
        </span>
        <em class="column-health health-${health.level}">${escapeHtml(health.label)}</em>
      </button>
      <div class="column-metrics">
        <div class="column-metric">
          <span><b>Missing</b><em>${missingPct}%</em></span>
          <div class="bar risk-bar"><i style="width:${missingPct}%"></i></div>
          <small>${missingCount.toLocaleString()} blank value${missingCount === 1 ? "" : "s"}</small>
        </div>
        <div class="column-metric">
          <span><b>Unique</b><em>${uniquePct}%</em></span>
          <div class="bar unique-bar"><i style="width:${uniquePct}%"></i></div>
          <small>${column.unique_count.toLocaleString()} distinct value${column.unique_count === 1 ? "" : "s"}</small>
        </div>
      </div>
      <div class="chip-row">
        <button data-rule-add="required" data-column="${escapeHtml(column.name)}">Required</button>
        <button data-rule-add="unique" data-column="${escapeHtml(column.name)}">Unique</button>
        <button data-rule-add="pii" data-column="${escapeHtml(column.name)}">PII</button>
        <button data-rule-add="exclude" data-column="${escapeHtml(column.name)}">Exclude ML</button>
      </div>
    `;
    grid.appendChild(card);
  });
  document.querySelectorAll("[data-open-column]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedColumn = button.dataset.openColumn;
      state.selectedIssueId = null;
      renderColumns();
      renderInspector();
    });
  });
  document.querySelectorAll("[data-rule-add]").forEach((button) => {
    button.addEventListener("click", () => addColumnRule(button.dataset.ruleAdd, button.dataset.column));
  });
}

function columnHealth(column, related) {
  const hasHighIssue = related.some((issue) => ["critical", "high"].includes(issue.severity));
  if (hasHighIssue || column.missing_rate >= 0.25) return { level: "risk", label: "Needs review" };
  if (column.missing_rate > 0 || related.length) return { level: "watch", label: "Watch" };
  return { level: "good", label: "Clean" };
}

function renderInspector() {
  const kind = document.querySelector("#inspectorKind");
  const content = document.querySelector("#inspectorContent");
  if (!state.audit) {
    kind.textContent = "context";
    content.innerHTML = '<p class="empty">Run an audit to inspect issues, columns, rules, and fixes.</p>';
    return;
  }
  if (state.selectedColumn) {
    const column = state.audit.profile.columns.find((item) => item.name === state.selectedColumn);
    const related = state.audit.issues.filter((issue) => issue.columns.includes(column.name));
    kind.textContent = "column";
    content.innerHTML = `
      <h3>${escapeHtml(column.name)}</h3>
      <p>${escapeHtml(column.inferred_type)} column with ${Math.round(column.missing_rate * 100)}% missing and ${column.unique_count} unique values.</p>
      <h4>Top values</h4>${renderTopValues(column)}
      <h4>Related issues</h4>${renderBullets(related.map((issue) => `${issue.id}: ${issue.title}`))}
    `;
    return;
  }
  const issue = state.audit.issues.find((item) => item.id === state.selectedIssueId) || state.audit.issues[0];
  if (!issue) {
    kind.textContent = "audit";
    content.innerHTML = '<p class="empty">No issues found.</p>';
    return;
  }
  kind.textContent = issue.id;
  content.innerHTML = `
    <h3>${escapeHtml(issue.title)}</h3>
    <p>${escapeHtml(issue.detail)}</p>
    <div class="inspector-meta">
      <span class="badge severity-${escapeHtml(issue.severity)}">${escapeHtml(issue.severity)}</span>
      <span class="badge">${escapeHtml(issue.category)}</span>
      <span class="badge">${escapeHtml(issue.status || "open")}</span>
    </div>
    <h4>Business impact</h4>
    <p>${escapeHtml(businessImpact(issue))}</p>
    <h4>Likely root cause</h4>
    <p>${escapeHtml(rootCause(issue))}</p>
    <h4>Recommendation</h4>
    <p>${escapeHtml(issue.recommendation)}</p>
    <h4>Examples</h4>
    ${renderExamples(issue.examples)}
  `;
}

async function updateIssueStatus(issueId, status) {
  const response = await fetch(`/audits/${state.audit.audit_id}/issues/${issueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  state.audit = await response.json();
  renderIssues();
  renderInspector();
  renderHistory();
  setStatus(`Issue ${issueId} marked ${status}.`);
}

async function bulkUpdateStatus(status) {
  if (!state.selectedIssueIds.size) return;
  for (const issueId of [...state.selectedIssueIds]) {
    await fetch(`/audits/${state.audit.audit_id}/issues/${issueId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
  }
  await openAudit(state.audit.audit_id);
  setStatus(`${state.selectedIssueIds.size} issues updated.`);
  state.selectedIssueIds.clear();
}

async function loadRemediation() {
  if (!state.audit) return;
  const response = await fetch(`/audits/${state.audit.audit_id}/remediation`);
  state.remediation = await response.json();
  state.remediationApplyResult = null;
  state.selectedActionIds = new Set(state.remediation.actions.map((action) => action.issue_id));
  renderRemediation();
}

function renderRemediation() {
  const actions = document.querySelector("#remediationActions");
  const script = document.querySelector("#cleaningScript");
  if (!state.remediation) {
    actions.innerHTML = '<p class="empty">Refresh remediation actions.</p>';
    script.textContent = "";
    return;
  }
  const groupLabels = { fill_missing: "Missing values", standardize: "Data consistency", mask: "Sensitive data", deduplicate: "Duplicates", validate: "Validation", review: "Review required", contract: "Contract alignment" };
  const grouped = state.remediation.actions.reduce((acc, action) => { (acc[action.action_type] ||= []).push(action); return acc; }, {});
  actions.innerHTML = Object.entries(grouped).map(([type, items]) => `
    <section class="remediation-action-group">
      <div class="remediation-action-group-title"><span>${escapeHtml(groupLabels[type] || titleCase(type))}</span><span>${items.length}</span></div>
      ${items.map(action => `<label class="remediation-action-row">
        <input type="checkbox" data-select-action="${escapeHtml(action.issue_id)}" ${state.selectedActionIds.has(action.issue_id) ? "checked" : ""}>
        <span><h3>${escapeHtml(action.title)}</h3><p>${escapeHtml(action.description)}</p><span class="remediation-action-meta"><i class="remediation-chip">${escapeHtml(titleCase(action.action_type))}</i>${action.requires_review ? '<i class="remediation-chip">Review</i>' : ''}</span></span>
        <i class="remediation-risk ${escapeHtml(action.risk)}">${escapeHtml(titleCase(action.risk))}</i>
      </label>`).join("")}
    </section>`).join("");
  document.querySelectorAll("[data-select-action]").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) state.selectedActionIds.add(box.dataset.selectAction); else state.selectedActionIds.delete(box.dataset.selectAction);
      renderSelectedScript(); updateRemediationSelectionCount();
      const previewStatus=document.querySelector("#remediationPreviewStatus"); if(previewStatus) previewStatus.textContent="Not previewed";
      const ready=document.querySelector("#remediationReadyState"); if(ready) ready.textContent="Ready to preview";
    });
  });
  updateRemediationSelectionCount();
  renderSelectedScript();
}

function updateRemediationSelectionCount() {
  const total = state.remediation?.actions.length || 0;
  const selected = state.selectedActionIds.size;
  const count = document.querySelector("#remediationSelectionCount");
  if (count) count.textContent = `${selected} of ${total} fixes selected`;
  const fixable = document.querySelector("#remediationFixableIssues");
  if (fixable) fixable.textContent = String(total);
}

function renderSelectedScript() {
  if (!state.remediation) return;
  const selected = state.remediation.actions.filter((action) => state.selectedActionIds.has(action.issue_id));
  document.querySelector("#cleaningScript").textContent = [
    "import pandas as pd",
    "",
    `df = pd.read_csv(${state.audit.dataset_name ? JSON.stringify(state.audit.dataset_name) : "'dataset.csv'"})`,
    "",
    "# Selected remediation draft. Review before running on production data.",
    ...selected.flatMap((action) => ["", `# ${action.issue_id}: ${action.title}`, action.pandas_code]),
    "",
    "df.to_csv('cleaned_dataset.csv', index=False)",
  ].join("\n");
}

function remediationPayload() {
  return {
    issue_ids: [...state.selectedActionIds],
    fill_strategy: document.querySelector("#remediationFillStrategy")?.value || "mode",
    mask_sensitive: Boolean(document.querySelector("#remediationMaskSensitive")?.checked),
  };
}

async function previewRemediation() {
  if (!state.audit || !state.selectedActionIds.size) { setStatus("Select at least one remediation action."); return; }
  const button = els.previewRemediationButton;
  button.disabled = true; button.textContent = "Previewing...";
  try {
    const response = await fetch(`/audits/${state.audit.audit_id}/remediation/preview`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(remediationPayload()),
    });
    const data = await parseResponse(response);
    renderRemediationPreview(data);
    setRemediationStep(2);
    setStatus("Remediation impact preview generated.");
  } catch (error) { setStatus(error.message || "Could not preview remediation."); }
  finally { button.disabled = false; button.textContent = "Preview impact"; }
}

function formatSignedNumber(value, suffix = "") {
  const numeric = Number(value) || 0;
  if (numeric > 0) return `+${numeric}${suffix}`;
  if (numeric < 0) return `\u2212${Math.abs(numeric)}${suffix}`;
  return `0${suffix}`;
}

function renderRemediationPreview(data) {
  state.remediationPreview = data;
  const scoreDelta = Number(data.projected_score_delta) || 0;
  const scoreDeclines = scoreDelta < 0;
  const status = document.querySelector("#remediationPreviewStatus");
  status.textContent = scoreDeclines ? "Risk review required" : "Preview ready";
  status.classList.toggle("warning", scoreDeclines);
  const ready=document.querySelector("#remediationReadyState");
  if(ready) {
    ready.textContent=scoreDeclines ? "Risk review required" : "Preview ready";
    ready.classList.toggle("warning", scoreDeclines);
  }
  const applyButton = els.applyRemediationButton;
  if (applyButton) {
    applyButton.classList.toggle("risk-action", scoreDeclines);
    applyButton.setAttribute("aria-label", scoreDeclines ? `Apply changes despite a projected score decrease of ${Math.abs(scoreDelta)} points` : "Apply remediation to a dataset copy");
  }
  const projected=document.querySelector("#remediationProjectedScore"); if(projected) projected.textContent=String(data.projected_score);
  const reduction = data.issues_before ? Math.round(((data.issues_before-data.projected_issues)/data.issues_before)*100) : 0;
  const reductionEl=document.querySelector("#remediationEstimatedReduction"); if(reductionEl) reductionEl.textContent=`${reduction}% (${data.issues_before-data.projected_issues} issues)`;
  const scoreDeltaClass = scoreDeclines ? "negative" : (scoreDelta > 0 ? "positive" : "neutral");
  document.querySelector("#remediationMetrics").innerHTML = `
    <div class="remediation-comparison-head"><span></span><span>Before</span><span>After</span><span>Change</span></div>
    <div class="remediation-comparison-row"><span>Reliability score</span><span>${data.score_before}/100</span><span>${data.projected_score}/100</span><em class="${scoreDeltaClass}">${formatSignedNumber(scoreDelta, " pts")}</em></div>
    <div class="remediation-comparison-row"><span>Issue count</span><span>${data.issues_before}</span><span>${data.projected_issues}</span><em>${formatSignedNumber(data.projected_issues-data.issues_before)}</em></div>
    <div class="remediation-comparison-row"><span>Changed cells</span><span>0</span><span>${data.changed_cells}</span><em>${formatSignedNumber(data.changed_cells)}</em></div>
    <div class="remediation-comparison-row"><span>Removed rows</span><span>0</span><span>${data.removed_rows}</span><span class="${data.removed_rows ? 'negative' : ''}">${formatSignedNumber(data.removed_rows)}</span></div>`;
  const riskWarning = scoreDeclines ? `<div class="remediation-score-risk"><span>Projected score decrease</span><p>The selected actions are expected to reduce the reliability score from ${data.score_before} to ${data.projected_score} (${formatSignedNumber(scoreDelta, " points")}). Review the transformations before applying them.</p></div>` : "";
  const reviewWarnings = data.warnings.length ? `<div class="remediation-warning"><span>Review-only actions</span><ul>${data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul></div>` : "";
  document.querySelector("#remediationWarnings").innerHTML = `${riskWarning}${reviewWarnings}`;
  document.querySelector("#remediationSeverityChart").innerHTML = `
    <p>Estimated issue reduction</p>
    ${[["High",Math.max(data.issues_before,1),Math.max(data.projected_issues,0)],["Medium",Math.max(Math.round(data.issues_before*.55),1),Math.max(Math.round(data.projected_issues*.55),0)],["Low",Math.max(Math.round(data.issues_before*.25),1),Math.max(Math.round(data.projected_issues*.25),0)]].map(([label,before,after])=>`<div class="severity-bar-row"><span>${label}</span><span class="severity-bars"><i style="width:${Math.min(100,before/Math.max(data.issues_before,1)*100)}%"></i><i class="after" style="width:${Math.min(100,after/Math.max(data.issues_before,1)*100)}%"></i></span><span>${after}</span></div>`).join("")}`;
  document.querySelector("#remediationSampleChanges").innerHTML = data.sample_changes.length ? `
    <div class="table-scroll"><table class="data-table"><thead><tr><th>Row</th><th>Column</th><th>Before</th><th>After</th></tr></thead><tbody>${data.sample_changes.map(c => `<tr><td>${escapeHtml(String(c.row))}</td><td>${escapeHtml(c.column)}</td><td>${escapeHtml(c.before ?? "Null")}</td><td>${escapeHtml(c.after ?? "Null")}</td></tr>`).join("")}</tbody></table></div>` : '<p class="empty">No deterministic cell changes are available for the selected actions.</p>';
}

let remediationRiskDialogResolver = null;

function resolveRemediationRiskDialog(confirmed) {
  if (!els.remediationRiskDialog || els.remediationRiskDialog.classList.contains("hidden")) return;
  els.remediationRiskDialog.classList.add("hidden");
  document.body.classList.remove("modal-open");
  const resolver = remediationRiskDialogResolver;
  remediationRiskDialogResolver = null;
  resolver?.(Boolean(confirmed));
}

function requestRemediationRiskApproval(preview) {
  const delta = Number(preview.projected_score_delta) || 0;
  document.querySelector("#remediationRiskCurrentScore").textContent = `${preview.score_before}/100`;
  document.querySelector("#remediationRiskProjectedScore").textContent = `${preview.projected_score}/100`;
  document.querySelector("#remediationRiskScoreDelta").textContent = formatSignedNumber(delta, " points");
  document.querySelector("#remediationRiskDialogSummary").textContent = `The projected score will decrease from ${preview.score_before} to ${preview.projected_score}.`;
  els.remediationRiskAcknowledgement.checked = false;
  els.confirmRemediationRiskDialog.disabled = true;
  els.remediationRiskDialog.classList.remove("hidden");
  document.body.classList.add("modal-open");
  setTimeout(() => els.remediationRiskAcknowledgement.focus(), 0);
  return new Promise((resolve) => { remediationRiskDialogResolver = resolve; });
}

async function applyRemediation() {
  if (!state.audit || !state.selectedActionIds.size) { setStatus("Select at least one remediation action."); return; }
  const button = els.applyRemediationButton;
  button.disabled = true; button.textContent = "Checking impact...";
  try {
    const previewResponse = await fetch(`/audits/${state.audit.audit_id}/remediation/preview`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(remediationPayload()),
    });
    const preview = await parseResponse(previewResponse);
    renderRemediationPreview(preview);
    if (Number(preview.projected_score_delta) < 0) {
      const confirmed = await requestRemediationRiskApproval(preview);
      if (!confirmed) {
        setStatus("Remediation apply cancelled. Review the selected actions.");
        return;
      }
    }
    button.textContent = "Applying...";
    const response = await fetch(`/audits/${state.audit.audit_id}/remediation/apply`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(remediationPayload()),
    });
    const data = await parseResponse(response);
    state.remediationApplyResult = data;
    renderRemediationApplyResult(data);
    await loadHistory();
    setRemediationStep(4);
    setStatus(`Corrected dataset created and audited automatically. Score: ${data.corrected_audit.score.overall}/100.`);
  } catch (error) { setStatus(error.message || "Could not apply remediation."); }
  finally { button.disabled = false; button.textContent = "Apply to dataset copy"; }
}

function setRemediationStep(activeStep) {
  document.querySelectorAll(".remediation-steps > span").forEach((step, index) => {
    const number = index + 1;
    step.classList.toggle("active", number === activeStep);
    step.classList.toggle("complete", number < activeStep);
  });
}

function renderRemediationApplyResult(data) {
  const result = document.querySelector("#remediationApplyResult");
  const exportButton = document.querySelector("#remediationExportPlaceholder");
  const ready = document.querySelector("#remediationReadyState");
  const corrected = data.corrected_audit;
  result.innerHTML = `<div class="remediation-success">
    <span>Dataset copy created and audited</span>
    <p>${data.applied_actions} actions applied \u00b7 ${data.changed_cells} cells changed \u00b7 ${data.removed_rows} rows removed.</p>
    <dl class="remediation-result-summary">
      <div><dt>Corrected dataset</dt><dd>${escapeHtml(corrected.dataset_name)}</dd></div>
      <div><dt>Actual score</dt><dd>${corrected.score.overall}/100</dd></div>
      <div><dt>Remaining issues</dt><dd>${corrected.issues.filter(issue => !["fixed","resolved","ignored"].includes(issue.status)).length}</dd></div>
    </dl>
    <button id="openCorrectedAuditButton" type="button">Open corrected audit</button>
  </div>`;
  exportButton.disabled = false;
  exportButton.classList.remove("hidden");
  ready.textContent = "Applied and validated";
  ready.classList.remove("warning");
  document.querySelector("#openCorrectedAuditButton")?.addEventListener("click", openCorrectedAudit);
}

async function exportCleanedCsv() {
  const result = state.remediationApplyResult;
  if (!result?.download_url) { setStatus("Apply remediation before exporting the cleaned CSV."); return; }
  const button = document.querySelector("#remediationExportPlaceholder");
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = "Preparing export...";
  try {
    const response = await fetch(result.download_url);
    if (!response.ok) throw new Error(await response.text() || "Cleaned CSV export failed.");
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename\*?=(?:UTF-8''|\")?([^;\"]+)/i);
    const filename = match ? decodeURIComponent(match[1].replace(/\"/g, "").trim()) : result.corrected_audit.dataset_name;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove();
    URL.revokeObjectURL(url);
    setStatus("Cleaned CSV exported.");
  } catch (error) { setStatus(error.message || "Could not export the cleaned CSV."); }
  finally { button.disabled = false; button.textContent = originalText; }
}

async function openCorrectedAudit() {
  const auditId = state.remediationApplyResult?.corrected_audit?.audit_id;
  if (!auditId) { setStatus("The corrected audit is not available."); return; }
  const url = new URL(window.location.href);
  url.searchParams.set("page", "audit");
  url.searchParams.set("audit", auditId);
  window.history.pushState({}, "", url);
  openAuditPage();
  try {
    await openAudit(auditId);
    renderAuditWorkspaceV2(state.audit);
    setStatus("Corrected audit opened.");
  } catch (error) {
    setStatus(error.message || "Could not open the corrected audit.");
  }
}

async function loadContract() {
  if (!state.audit) return;
  const response = await fetch(`/audits/${state.audit.audit_id}/contract`);
  state.contract = await response.json();
  document.querySelector("#contractOutput").textContent = JSON.stringify(state.contract, null, 2);
  renderContractMini();
}

function useContractAsRules() {
  if (!state.contract) return;
  const rules = {
    required_columns: state.contract.required_columns,
    unique_columns: state.contract.unique_columns,
    expected_types: state.contract.expected_types,
    allowed_values: state.contract.allowed_values,
    numeric_ranges: state.contract.numeric_ranges,
    date_ranges: state.contract.date_ranges,
    stale_after_days: state.contract.freshness_rules || {},
  };
  els.rulesInput.value = JSON.stringify(rules, null, 2);
  hydrateRuleBuilder(rules);
  activateTab("rules");
  setStatus("Contract copied into rule builder.");
}

function renderContractMini() {
  const target = document.querySelector("#contractMini");
  if (!state.contract) {
    target.innerHTML = '<p class="empty">Generate a contract from an audit.</p>';
    return;
  }
  target.innerHTML = `
    <span>${state.contract.required_columns.length} required columns</span>
    <span>${state.contract.unique_columns.length} unique keys</span>
    <span>${state.contract.pii_columns.length} PII fields</span>
  `;
}

async function compareAudits() {
  if (!state.audit || !els.baselineSelect.value) return;
  const response = await fetch(`/audits/compare/${els.baselineSelect.value}/${state.audit.audit_id}`);
  const comparison = await response.json();
  document.querySelector("#comparisonOutput").innerHTML = `
    <div class="metric-row">
      <div class="${comparison.score_delta >= 0 ? "positive" : "negative"}"><span>Score delta</span><strong>${signed(comparison.score_delta)}</strong></div>
      <div class="${comparison.issue_count_delta <= 0 ? "positive" : "negative"}"><span>Issue delta</span><strong>${signed(comparison.issue_count_delta)}</strong></div>
    </div>
    <div class="diff-grid">
      <section><h3>New Issues</h3>${renderBullets(comparison.new_issues.map((issue) => issue.title))}</section>
      <section><h3>Resolved Issues</h3>${renderBullets(comparison.resolved_issues.map((issue) => issue.title))}</section>
      <section><h3>Improved Columns</h3>${renderBullets(comparison.improved_columns)}</section>
      <section><h3>Worsened Columns</h3>${renderBullets(comparison.worsened_columns)}</section>
    </div>
    <h3>Schema Changes</h3><pre>${escapeHtml(JSON.stringify(comparison.schema_changes, null, 2))}</pre>
  `;
}

async function askAnalyst(questionOverride) {
  const question = typeof questionOverride === "string" ? questionOverride : els.analystQuestion.value.trim();
  if (!state.audit || !question) return;
  state.chat.push({ role: "user", text: question });
  renderChat();
  els.askAnalystButton.disabled = true;
  try {
    const response = await fetch(`/audits/${state.audit.audit_id}/analyst`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: analystHistory() }),
    });
    const payload = await response.json();
    if (!response.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : "Analyst could not answer that question.";
      throw new Error(detail);
    }
    state.chat.push({
      role: "assistant",
      text: payload.answer || "I could not generate an answer for that question.",
      source: payload.source,
      issueIds: payload.supporting_issue_ids,
    });
    els.analystQuestion.value = "";
  } catch (error) {
    state.chat.push({ role: "assistant", text: error.message || "Analyst request failed." });
  } finally {
    els.askAnalystButton.disabled = state.busy;
    renderChat();
  }
}

function analystHistory() {
  return state.chat
    .slice(0, -1)
    .slice(-8)
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({ role: message.role, text: message.text }));
}

function renderChat() {
  const thread = document.querySelector("#chatThread");
  thread.innerHTML = state.chat.length ? "" : '<p class="empty">Ask a question or use a suggested prompt.</p>';
  state.chat.forEach((message) => {
    const item = document.createElement("article");
    item.className = `chat-message ${message.role}`;
    item.innerHTML = `
      <p>${escapeHtml(message.text)}</p>
      ${message.issueIds ? `<div class="chip-row">${message.issueIds.map((id) => `<button data-cited-issue="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join("")}</div>` : ""}
    `;
    thread.appendChild(item);
  });
  document.querySelectorAll("[data-cited-issue]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedIssueId = button.dataset.citedIssue;
      activateTab("issues");
      renderIssues();
      renderInspector();
    });
  });
}

function renderPromptChips() {
  const prompts = [
    "What should I fix first?",
    "Can I use this for machine learning?",
    "Which fields should I protect before sharing?",
    "How do I improve the score?",
    "What should I report to a manager?",
    "What contract rules should I add?",
  ];
  document.querySelector("#promptChips").innerHTML = prompts.map((prompt) => `<button data-prompt="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>`).join("");
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => askAnalyst(button.dataset.prompt));
  });
}

function regenerateSummary() {
  if (!state.audit) return;
  runAudit(`/audits/${state.audit.audit_id}/summary/regenerate`, { method: "POST" });
}

function activateTab(name) {
  if (!state.audit && name !== "rules") return;
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${name}`));
  if (name === "remediation" && !state.remediation) loadRemediation();
  if (name === "contract" && !state.contract) loadContract();
}

function applyScoreFilter(filter) {
  if (filter === "all") {
    state.filters.category = "all";
    state.filters.severity = "all";
  } else if (filter === "privacy") {
    state.filters.category = "privacy";
  } else {
    state.filters.category = filter;
  }
  els.categoryFilter.value = [...els.categoryFilter.options].some((option) => option.value === state.filters.category) ? state.filters.category : "all";
  activateTab("issues");
  renderIssues();
}

function syncRulesFromBuilder(showStatus = true) {
  const rules = {
    required_columns: splitCsv(document.querySelector("#requiredColumnsInput").value),
    unique_columns: splitCsv(document.querySelector("#uniqueColumnsInput").value),
    allowed_values: parseKeyValues(document.querySelector("#allowedValuesInput").value, "list"),
    numeric_ranges: parseKeyValues(document.querySelector("#numericRangesInput").value, "range"),
    date_ranges: parseKeyValues(document.querySelector("#dateRangesInput").value, "dateRange"),
    stale_after_days: parseKeyValues(document.querySelector("#freshnessInput").value, "number"),
  };
  els.rulesInput.value = JSON.stringify(rules, null, 2);
  if (showStatus) setStatus("Rule JSON synced from builder.");
}

function hydrateRuleBuilder(rules) {
  document.querySelector("#requiredColumnsInput").value = (rules.required_columns || []).join(", ");
  document.querySelector("#uniqueColumnsInput").value = (rules.unique_columns || []).join(", ");
  document.querySelector("#allowedValuesInput").value = Object.entries(rules.allowed_values || {}).map(([key, values]) => `${key}=${values.join(",")}`).join("\n");
  document.querySelector("#numericRangesInput").value = Object.entries(rules.numeric_ranges || {}).map(([key, value]) => `${key}=${value.min ?? ""}:${value.max ?? ""}`).join("\n");
  document.querySelector("#dateRangesInput").value = Object.entries(rules.date_ranges || {}).map(([key, value]) => `${key}=${value.min ?? ""}:${value.max ?? ""}`).join("\n");
  document.querySelector("#freshnessInput").value = Object.entries(rules.stale_after_days || {}).map(([key, value]) => `${key}=${value}`).join("\n");
}

function switchRuleMode(mode) {
  document.querySelectorAll("[data-rule-mode]").forEach((button) => button.classList.toggle("active", button.dataset.ruleMode === mode));
  document.querySelector(".rule-builder").classList.toggle("hidden", mode === "json");
  els.rulesInput.classList.toggle("expanded", mode === "json");
}

function addColumnRule(kind, column) {
  if (kind === "required") appendCsvValue("#requiredColumnsInput", column);
  if (kind === "unique") appendCsvValue("#uniqueColumnsInput", column);
  if (kind === "pii") setStatus(`${column} marked for privacy review in inspector.`);
  if (kind === "exclude") setStatus(`${column} noted as unsuitable for ML.`);
  syncRulesFromBuilder(false);
}

function renderCompareOptions() {
  els.baselineSelect.innerHTML = state.history
    .filter((audit) => !state.audit || audit.audit_id !== state.audit.audit_id)
    .map((audit) => `<option value="${escapeHtml(audit.audit_id)}">${escapeHtml(audit.dataset_name)} - ${audit.score}/100</option>`)
    .join("");
}

function toggleAllIssues() {
  const issues = filteredIssues();
  if (els.selectAllIssues.checked) issues.forEach((issue) => state.selectedIssueIds.add(issue.id));
  else issues.forEach((issue) => state.selectedIssueIds.delete(issue.id));
  renderIssues();
}

function copySelectedScript() {
  const text = document.querySelector("#cleaningScript").textContent;
  navigator.clipboard?.writeText(text);
  setStatus("Selected cleaning script copied.");
}

function copyActionCode(issueId) {
  const action = state.remediation?.actions.find((item) => item.issue_id === issueId);
  if (!action) return;
  navigator.clipboard?.writeText(action.pandas_code);
  setStatus(`${issueId} code copied.`);
}

function setMeter(selector, value) {
  document.querySelector(selector).style.width = `${value}%`;
}

function privacyColumns(audit) {
  return [...new Set(audit.issues.filter((issue) => issue.category === "privacy").flatMap((issue) => issue.columns))];
}

function businessImpact(issue) {
  const impacts = {
    privacy: "Compliance and data-sharing risk. Sensitive values should be masked before exports or LLM use.",
    uniqueness: "Entity counts, customer views, and model training splits can be distorted by duplicate records.",
    validity: "Reports and downstream automations may act on malformed or impossible values.",
    completeness: "Missing values reduce trust and can break segmentation, outreach, or model features.",
    anomaly: "Outliers can skew averages, thresholds, forecasts, and model behavior.",
    schema: "Pipeline consumers may fail when expected fields or types are missing.",
    integrity: "Lifecycle metrics and operational workflows can become logically inconsistent.",
    timeliness: "Stale records can produce outdated reporting and poor operational decisions.",
    consistency: "Aggregations can split one business concept into multiple labels.",
  };
  return impacts[issue.category] || "This issue can reduce reliability for reporting, operations, or analytics.";
}

function rootCause(issue) {
  if (issue.category === "schema") return "Likely export mapping, upstream schema drift, or missing source-system field.";
  if (issue.category === "uniqueness") return "Likely duplicate ingestion, repeated exports, or an unclear business key.";
  if (issue.category === "validity") return "Likely weak input validation, inconsistent formatting, or transformation parsing errors.";
  if (issue.category === "completeness") return "Likely optional capture, failed joins, or incomplete source records.";
  if (issue.category === "consistency") return "Likely free-text entry, multiple systems, or missing canonical mapping.";
  if (issue.category === "privacy") return "Likely raw operational data is being reused beyond its original access boundary.";
  return "Review source records and upstream transformation steps to confirm whether this is systemic or isolated.";
}

function renderTopValues(column) {
  const values = column.stats?.top_values || [];
  return values.length ? `<ul>${values.map((item) => `<li>${escapeHtml(item.value)} <span>${item.count}</span></li>`).join("")}</ul>` : '<p class="empty">No top values available.</p>';
}

function renderExamples(examples) {
  if (!examples || !examples.length) return '<p class="empty">No row examples captured.</p>';
  return `<div class="examples">${examples.map((example) => `<pre>${escapeHtml(JSON.stringify(example, null, 2))}</pre>`).join("")}</div>`;
}

function renderList(selector, values) {
  document.querySelector(selector).innerHTML = (values || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("");
}

function renderBullets(values) {
  return values && values.length ? `<ul>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>` : '<p class="empty">None.</p>';
}

function fillSelect(select, label, values) {
  const current = select.value;
  select.innerHTML = `<option value="all">${label}</option>` + values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  select.value = [...select.options].some((option) => option.value === current) ? current : "all";
}

function statusOptions(current) {
  return ["open", "triaged", "in_progress", "blocked", "resolved", "accepted_risk", "ignored"].map((status) => `<option value="${status}" ${status === current ? "selected" : ""}>${capitalizeV2(status)}</option>`).join("");
}

function splitCsv(value) {
  return value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean);
}

function parseKeyValues(text, mode) {
  const output = {};
  text.split("\n").map((line) => line.trim()).filter(Boolean).forEach((line) => {
    const [key, raw = ""] = line.split("=");
    if (!key) return;
    if (mode === "list") output[key.trim()] = raw.split(",").map((item) => item.trim()).filter(Boolean);
    if (mode === "range" || mode === "dateRange") {
      const [min, max] = raw.split(":");
      output[key.trim()] = {
        min: min ? (mode === "range" ? Number(min) : min) : null,
        max: max ? (mode === "range" ? Number(max) : max) : null,
      };
    }
    if (mode === "number") output[key.trim()] = Number(raw);
  });
  return output;
}

function appendCsvValue(selector, value) {
  const input = document.querySelector(selector);
  const values = new Set(splitCsv(input.value));
  values.add(value);
  input.value = [...values].join(", ");
}

function signed(value) {
  return value > 0 ? `+${value}` : String(value);
}

function setStatus(message) {
  const detail = message?.detail;
  const normalized = typeof message === "string"
    ? message
    : Array.isArray(detail)
      ? detail.map((item) => item?.msg || item?.message || "Request validation failed.").join(" ")
      : message?.message || (typeof detail === "string" ? detail : null) || (message == null ? "" : "The requested action could not be completed.");
  els.statusText.textContent = normalized;
  els.statusText.title = normalized;
  els.statusText.classList.toggle("status-error", /error|failed|unable|invalid|could not/i.test(normalized));
  els.statusText.classList.toggle("status-success", /success|completed|created|updated|saved|ready/i.test(normalized));
}

function setBusy(isBusy) {
  state.busy = isBusy;
  if (els.fileInput) els.fileInput.disabled = isBusy;
  [
    els.uploadButton,
    els.sampleButton,
    els.emptySampleButton,
    els.regenerateButton,
    els.loadRemediationButton,
    els.loadContractButton,
    els.compareButton,
    els.askAnalystButton,
  ].forEach((button) => {
    if (button) button.disabled = isBusy;
  });
  if (els.uploadButton) els.uploadButton.textContent = isBusy ? "Auditing..." : "Upload CSV";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll("[data-open-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    const tab = document.querySelector(`.tab[data-tab="${button.dataset.openTab}"]`);
    if (tab) tab.click();
  });
});


function hideAllPages() {
  ["#overviewPage", "#auditPage", "#datasetsPage", "#versionsPage", "#driftPage", "#schedulesPage", "#alertsPage", "#connectorsPage", "#copilotPage", "#reportsPage", "#rulesPage", "#teamPage", "#remediationPage"].forEach(selector => document.querySelector(selector)?.classList.add("hidden"));
  [authEls.overviewNavButton, authEls.auditNavButton, authEls.datasetsNavButton, document.querySelector("#versionsNavButton"), document.querySelector("#driftNavButton"), document.querySelector("#schedulesNavButton"), document.querySelector("#alertsNavButton"), document.querySelector("#connectorsNavButton"), document.querySelector("#copilotNavButton"), document.querySelector("#reportsNavButton"), authEls.teamNavButton, authEls.rulesNavButton, authEls.remediationNavButton].forEach(button => button?.classList.remove("active"));
}

function animatePage(page) {
  page.classList.remove("hidden", "page-enter");
  void page.offsetWidth;
  page.classList.add("page-enter");
}

function openOverviewPage() {
  authEls.profileMenu.classList.add("hidden");
  hideAllPages();
  animatePage(document.querySelector("#overviewPage"));
  authEls.overviewNavButton.classList.add("active");
  renderOverview();
}

async function openRulesPage() {
  authEls.profileMenu.classList.add("hidden");
  hideAllPages();
  animatePage(document.querySelector("#rulesPage"));
  authEls.rulesNavButton.classList.add("active");
  await loadRulesWorkspace();
}

async function openTeamPage() {
  authEls.profileMenu.classList.add("hidden");
  hideAllPages();
  animatePage(authEls.teamPage);
  authEls.teamNavButton.classList.add("active");
  await loadTeam();
}

function openAuditPage() {
  hideAllPages();
  const auditPage = document.querySelector("#auditPage");
  animatePage(auditPage);
  authEls.auditNavButton.classList.add("active");
  const requestedAuditId = new URL(window.location.href).searchParams.get("audit");
  if (requestedAuditId && state.audit?.audit_id !== requestedAuditId) {
    openAudit(requestedAuditId).catch(() => setStatus("Unable to load the requested audit."));
  }
  if (auditV2.dashboard) {
    auditV2.dashboard.classList.toggle("hidden", !state.audit);
    auditV2.empty.classList.toggle("hidden", Boolean(state.audit));
    if (state.audit) renderAuditWorkspaceV2(state.audit);
  }
}

async function openRemediationPage() {
  authEls.profileMenu.classList.add("hidden");
  hideAllPages();
  const remediationPage = document.querySelector("#remediationPage");
  animatePage(remediationPage);
  authEls.remediationNavButton.classList.add("active");
  const noAudit = document.querySelector("#remediationNoAudit");
  const workspace = document.querySelector("#tab-remediation");
  noAudit?.classList.toggle("hidden", Boolean(state.audit));
  workspace?.classList.toggle("hidden", !state.audit);
  if (!state.audit) {
    setStatus("Select a completed audit before creating a remediation task.");
    return;
  }
  workspace?.classList.remove("hidden");
  const datasetName = state.audit.dataset_name || "Selected dataset";
  const dateValue = state.audit.created_at ? formatDateTime(state.audit.created_at) : "Latest completed run";
  const scoreValue = state.audit.score?.overall ?? state.audit.score ?? "\u2014";
  const datasetEl=document.querySelector("#remediationDatasetName"); if(datasetEl) datasetEl.textContent=datasetName;
  const dateEl=document.querySelector("#remediationAuditDate"); if(dateEl) dateEl.textContent=dateValue;
  const scoreEl=document.querySelector("#remediationCurrentScore"); if(scoreEl) scoreEl.textContent=String(scoreValue);
  const outputEl=document.querySelector("#remediationOutputName"); if(outputEl) outputEl.value=`cleaned_${datasetName}`;
  await loadRemediation();
  setStatus(`Remediation workspace loaded for ${state.audit.dataset_name}.`);
}

function openAuditTab(tabName) {
  if (tabName === "remediation") { navigateToPage("remediation"); return; }
  openAuditPage();
  activateTab(tabName);
  if (tabName === "rules") authEls.rulesNavButton.classList.add("active");
}

async function loadTeam() {
  const role = state.currentUser?.membership_role;
  const canManage = ["owner", "admin"].includes(role);
  authEls.inviteForm.classList.toggle("hidden", !canManage);
  authEls.teamPermissionNote.textContent = canManage ? "Invite colleagues and manage organization-level access." : "You can view team membership. Owner or admin access is required to make changes.";
  const membersResponse = await fetch("/team/members");
  if (!membersResponse.ok) return;
  const members = await membersResponse.json();
  authEls.teamMembers.innerHTML = members.map(member => `
    <div class="team-row">
      <div><strong>${escapeHtml(member.full_name)}</strong><small>${escapeHtml(member.email)}</small></div>
      <div><span class="status-${member.is_active ? "active" : "inactive"}">${member.is_active ? "Active" : "Inactive"}</span><small>${member.last_login_at ? `Last login ${new Date(member.last_login_at).toLocaleString()}` : "Never signed in"}</small></div>
      <select data-role-membership="${member.membership_id}" ${canManage ? "" : "disabled"}>${["owner","admin","analyst","viewer"].map(r=>`<option value="${r}" ${r===member.role?"selected":""}>${r}</option>`).join("")}</select>
      <div class="team-actions">${canManage && member.user_id !== state.currentUser?.id ? `<button class="secondary-button" data-toggle-member="${member.membership_id}" data-active="${member.is_active}">${member.is_active ? "Deactivate" : "Activate"}</button>` : ""}</div>
    </div>`).join("") || '<p class="empty">No members found.</p>';
  document.querySelectorAll("[data-role-membership]").forEach(select => select.addEventListener("change", () => updateMemberRole(select.dataset.roleMembership, select.value)));
  document.querySelectorAll("[data-toggle-member]").forEach(button => button.addEventListener("click", () => updateMemberStatus(button.dataset.toggleMember, button.dataset.active !== "true")));
  if (!canManage) { authEls.teamInvitations.innerHTML = '<p class="empty">Invitation history is available to owners and admins.</p>'; return; }
  const invitationsResponse = await fetch("/team/invitations");
  const invitations = invitationsResponse.ok ? await invitationsResponse.json() : [];
  authEls.teamInvitations.innerHTML = invitations.map(invite => `<div class="team-row"><div><strong>${escapeHtml(invite.full_name)}</strong><small>${escapeHtml(invite.email)}</small></div><div><span class="status-${invite.status}">${invite.status}</span><small>Expires ${new Date(invite.expires_at).toLocaleDateString()}</small></div><span class="chip">${escapeHtml(invite.role)}</span><div class="team-actions">${invite.status === "pending" ? `<button class="secondary-button" data-revoke-invite="${invite.id}">Revoke</button>` : ""}</div></div>`).join("") || '<p class="empty">No invitations yet.</p>';
  document.querySelectorAll("[data-revoke-invite]").forEach(button => button.addEventListener("click", () => revokeInvitation(button.dataset.revokeInvite)));
}

async function createInvitation(event) {
  event.preventDefault();
  const response = await fetch("/team/invitations", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({full_name:authEls.inviteName.value,email:authEls.inviteEmail.value,role:authEls.inviteRole.value})});
  const payload = await response.json().catch(()=>({}));
  if (!response.ok) {
    authEls.inviteResult.classList.remove("hidden", "success");
    authEls.inviteResult.classList.add("error");
    authEls.inviteResult.textContent = responseErrorMessage(payload, response.status).replace(/^Value error,\s*/i, "");
    return;
  }
  const url = `${window.location.origin}${payload.acceptance_path}`;
  authEls.inviteResult.classList.remove("hidden", "error");
  authEls.inviteResult.classList.add("success");
  authEls.inviteResult.innerHTML = `
    <strong>Invitation created</strong>
    <span>Share this secure one-time activation link with ${escapeHtml(payload.full_name)}.</span>
    <div class="invitation-link-row">
      <input type="text" value="${escapeHtml(url)}" readonly aria-label="Invitation link">
      <button type="button" class="secondary-button" data-copy-invitation-link>Copy link</button>
    </div>`;
  authEls.inviteResult.querySelector("[data-copy-invitation-link]")?.addEventListener("click", async (event) => {
    await navigator.clipboard.writeText(url);
    event.currentTarget.textContent = "Copied";
    setTimeout(() => { event.currentTarget.textContent = "Copy link"; }, 1600);
  });
  authEls.inviteForm.reset();
  await loadTeam();
}

async function updateMemberRole(id, role) {
  const response = await fetch(`/team/members/${id}/role`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({role})});
  if (!response.ok) { const payload=await response.json().catch(()=>({})); setStatus(payload.detail || "Unable to update role."); await loadTeam(); return; }
  setStatus("Team role updated."); await loadTeam();
}

async function updateMemberStatus(id, isActive) {
  const response = await fetch(`/team/members/${id}/status`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({is_active:isActive})});
  if (!response.ok) { const payload=await response.json().catch(()=>({})); setStatus(payload.detail || "Unable to update member status."); return; }
  setStatus("Member access updated."); await loadTeam();
}

async function revokeInvitation(id) {
  const response = await fetch(`/team/invitations/${id}`, {method:"DELETE"});
  if (!response.ok) { setStatus("Unable to revoke invitation."); return; }
  setStatus("Invitation revoked."); await loadTeam();
}

function bindDashboardShell() {
  document.querySelector("#overviewSampleButton")?.addEventListener("click", () => { openAuditPage(); runAudit("/audits/sample", {method:"POST"}); });
  document.querySelector("#sidebarSampleButton")?.addEventListener("click", () => { openAuditPage(); runAudit("/audits/sample", {method:"POST"}); });
  document.querySelector("#overviewRuleButton")?.addEventListener("click", async () => { navigateToPage("rules"); setTimeout(() => openRuleEditor(), 150); });
  document.querySelector("#sidebarRuleButton")?.addEventListener("click", async () => { navigateToPage("rules"); setTimeout(() => openRuleEditor(), 150); });
  document.querySelector("#overviewInviteButton")?.addEventListener("click", openTeamPage);
  document.querySelector("#sidebarInviteButton")?.addEventListener("click", openTeamPage);
  document.querySelector("#viewScoreButton")?.addEventListener("click", openAuditPage);
  document.querySelector("#viewIssuesButton")?.addEventListener("click", () => openAuditTab("issues"));
  document.querySelector("#viewAuditsButton")?.addEventListener("click", openAuditPage);
  document.querySelector("#manageWorkspaceButton")?.addEventListener("click", openAuditPage);
  document.querySelector("#nextStepButton")?.addEventListener("click", openAuditPage);
  document.querySelector("#overviewRefreshButton")?.addEventListener("click", loadHistory);
  document.querySelector("#historyRefreshVisible")?.addEventListener("click", loadHistory);
  const sidebar=document.querySelector("#sidebar");
  const setSidebarCollapsed=(collapsed)=>{
    document.body.classList.toggle("sidebar-collapsed",Boolean(collapsed));
    const toggle=document.querySelector("#sidebarToggleButton");
    const collapse=document.querySelector("#collapseSidebarButton");
    toggle?.setAttribute("aria-expanded",String(!collapsed));
    toggle?.setAttribute("aria-label",collapsed?"Expand navigation":"Collapse navigation");
    if(collapse){
      collapse.querySelector("span:last-child")?.replaceChildren(document.createTextNode(collapsed?"Expand":"Collapse"));
      collapse.setAttribute("aria-label",collapsed?"Expand navigation":"Collapse navigation");
    }
    try{localStorage.setItem("drc-sidebar-collapsed",collapsed?"1":"0")}catch{}
  };
  const toggleSidebar=()=>setSidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
  try{setSidebarCollapsed(localStorage.getItem("drc-sidebar-collapsed")==="1")}catch{setSidebarCollapsed(false)}
  document.querySelector("#mobileMenuButton")?.addEventListener("click", () => sidebar?.classList.toggle("open"));
  document.querySelector("#sidebarToggleButton")?.addEventListener("click",toggleSidebar);
  document.querySelector("#collapseSidebarButton")?.addEventListener("click",toggleSidebar);
  document.querySelectorAll(".nav-group-toggle").forEach(toggle=>toggle.addEventListener("click",()=>{
    if(document.body.classList.contains("sidebar-collapsed")&&window.innerWidth>800)return;
    const group=toggle.closest(".nav-group");
    const collapsed=group?.classList.toggle("is-collapsed")||false;
    toggle.setAttribute("aria-expanded",String(!collapsed));
  }));
  document.querySelectorAll(".grouped-nav .nav-item").forEach(item=>item.addEventListener("click",()=>{
    if(window.innerWidth<=800)sidebar?.classList.remove("open");
  }));
  document.querySelector("#overviewRunAuditButton")?.addEventListener("click", openAuditPage);
  document.querySelector("#overviewCriticalIssuesButton")?.addEventListener("click", () => { navigateToPage("alerts"); setTimeout(() => { const severity=document.querySelector("#alertSeverity"); if(severity){ severity.value="critical"; severity.dispatchEvent(new Event("change")); } }, 180); });
  document.querySelector("#overviewCopilotButton")?.addEventListener("click", () => navigateToPage("copilot"));
  document.querySelector("#overviewActivityRefresh")?.addEventListener("click", loadOverviewCommandCentre);
  document.querySelectorAll("[data-overview-nav]").forEach(button => button.addEventListener("click", () => {
    const target=button.dataset.overviewNav;
    if(target==="audit-issues") return openAuditTab("issues");
    navigateToPage(target);
  }));
  document.querySelectorAll("[data-overview-action]").forEach(button => button.addEventListener("click", async () => {
    const action=button.dataset.overviewAction;
    if(action==="audit") return openAuditPage();
    if(action==="rule"){ navigateToPage("rules"); return setTimeout(() => openRuleEditor(),180); }
    if(action==="dataset"){ navigateToPage("datasets"); return setTimeout(() => document.querySelector("#addDatasetButton")?.click(),180); }
    if(action==="remediation") return navigateToPage("remediation");
    if(action==="reports") return navigateToPage("reports");
    if(action==="copilot") return navigateToPage("copilot");
    if(action==="schedule"){ navigateToPage("schedules"); return setTimeout(() => openScheduleDialog(),180); }
    if(action==="contract"){ navigateToPage("rules"); return setTimeout(() => { document.querySelector('[data-rules-tab="contracts"]')?.click(); openContractEditor(); },220); }
  }));
  const emptyFile = document.querySelector("#emptyFileInput");
  emptyFile?.addEventListener("change", () => {
    if (!emptyFile.files.length) return;
    const dt = new DataTransfer(); dt.items.add(emptyFile.files[0]); els.fileInput.files = dt.files; uploadCsv();
  });
}

function setText(selector, value) {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
}

function overviewRelativeTime(value){
  if(!value)return "\u2014";
  const diff=new Date(value).getTime()-Date.now(),mins=Math.round(Math.abs(diff)/60000);
  if(mins<60)return diff>=0?`in ${mins} min`:`${mins} min ago`;
  const hours=Math.round(mins/60);if(hours<24)return diff>=0?`in ${hours} hr`:`${hours} hr ago`;
  const days=Math.round(hours/24);return diff>=0?`in ${days} day${days===1?'':'s'}`:`${days} day${days===1?'':'s'} ago`;
}
function overviewStatusClass(value){return ['critical','high','failed','warning'].includes(String(value).toLowerCase())?'danger':['success','completed','healthy','good'].includes(String(value).toLowerCase())?'success':'info'}
function renderOverview(){loadOverviewCommandCentre()}
async function loadOverviewCommandCentre(){
  const page=document.querySelector('#overviewPage');if(!page)return;
  try{
    const response=await fetch('/reports/overview'),payload=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'Unable to load the platform overview.');
    renderOverviewCommandCentre(payload);
  }catch(error){setStatus(error.message||'Unable to load the platform overview.');}
}
function renderOverviewCommandCentre(payload){
  const m=payload.metrics||{},severity=m.severity||{},ribbon=payload.ribbon||{},platform=payload.platform||{};
  const score=m.score==null?'\u2014':`${m.score} / 100`,delta=m.score_delta;
  setText('#overviewRibbonScore',score);setText('#overviewVisualScore',m.score==null?'\u2014':m.score);setText('#overviewScoreMetric',score);
  setText('#overviewRibbonTrend',delta==null?'Current workspace':`${delta>=0?'\u2191':'\u2193'} ${Math.abs(delta)} pts vs previous period`);
  setText('#overviewScoreChange',delta==null?'Latest completed audits':`${delta>=0?'\u2191':'\u2193'} ${Math.abs(delta)} points vs previous period`);
  setText('#overviewRibbonCritical',severity.critical||0);setText('#overviewRibbonRemediations',m.open_remediations||0);setText('#overviewRibbonOverdue',`${m.overdue_remediations||0} overdue-risk`);
  setText('#overviewRibbonNextRun',ribbon.next_run_at?new Date(ribbon.next_run_at).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'\u2014');setText('#overviewRibbonNextDataset',ribbon.next_schedule_name||'No active schedule');
  const visualRing=document.querySelector('#overviewVisualRing');if(visualRing)visualRing.style.setProperty('--overview-score',m.score||0);
  setText('#overviewDatasetMetric',m.datasets||0);setText('#overviewDatasetChange',`Across ${m.domains||0} domain${m.domains===1?'':'s'}`);
  setText('#overviewIssueMetric',m.active_issues||0);setText('#overviewIssueBreakdown',`${severity.critical||0} critical \u00b7 ${severity.high||0} high \u00b7 ${severity.medium||0} medium`);
  setText('#overviewFailedRuleMetric',m.failed_rules||0);setText('#overviewRuleFailureRate',`${m.rule_failure_rate||0}% failure rate`);
  setText('#overviewContractMetric',m.contract_violations||0);setText('#overviewContractImpact',`${m.contracts_impacted||0} contract${m.contracts_impacted===1?'':'s'} impacted`);
  setText('#overviewDriftMetric',m.drift_events||0);setText('#overviewDriftImpact',`${m.drift_datasets||0} dataset${m.drift_datasets===1?'':'s'} affected`);
  setText('#overviewRemediationMetric',m.open_remediations||0);setText('#overviewRemediationOverdue',`${m.overdue_remediations||0} overdue-risk`);
  const lifecycle=document.querySelector('#overviewLifecycleRows'),life=payload.lifecycle||[];
  if(lifecycle)lifecycle.innerHTML=`<div class="lifecycle-row lifecycle-head"><span>Status</span><span>Count</span><span>Critical</span><span>High</span></div>`+life.map(row=>`<div class="lifecycle-row"><strong>${escapeHtml(titleCase(row.status.replace('_',' ')))}</strong><span>${row.count}</span><span>${row.critical}</span><span>${row.high}</span></div>`).join('')+`<div class="lifecycle-row lifecycle-total"><strong>Total</strong><span>${life.reduce((s,r)=>s+r.count,0)}</span><span>${severity.critical||0}</span><span>${severity.high||0}</span></div>`;
  const totalSeverity=Object.values(severity).reduce((s,v)=>s+Number(v||0),0),donut=document.querySelector('#overviewIssueDonut');
  if(donut){const critical=(severity.critical||0)*100/Math.max(totalSeverity,1),high=(severity.high||0)*100/Math.max(totalSeverity,1),medium=(severity.medium||0)*100/Math.max(totalSeverity,1);donut.style.background=`conic-gradient(#ef5b55 0 ${critical}%,#f58b45 ${critical}% ${critical+high}%,#f4c342 ${critical+high}% ${critical+high+medium}%,#27a875 ${critical+high+medium}% 100%)`}
  setText('#overviewDonutTotal',totalSeverity);
  const legend=document.querySelector('#overviewSeverityLegend');if(legend)legend.innerHTML=['critical','high','medium','low'].map(name=>`<div><i class="legend-${name}"></i><span>${titleCase(name)}</span><strong>${severity[name]||0}</strong></div>`).join('');
  const activity=document.querySelector('#overviewActivityList');if(activity)activity.innerHTML=(payload.activity||[]).map(item=>`<button class="overview-list-item" data-activity-kind="${escapeHtml(item.kind)}" data-activity-reference="${escapeHtml(item.reference||'')}" data-activity-dataset="${item.dataset_id||''}"><i class="${overviewStatusClass(item.status)}">${item.kind==='audit'?'\u2713':item.kind==='rule'?'\u25a7':item.kind==='contract'?'\u25a8':'\u25a4'}</i><span><strong>${escapeHtml(item.title)}</strong><small>${item.time?new Date(item.time).toLocaleString():'\u2014'}</small></span><em class="${overviewStatusClass(item.status)}">${escapeHtml(titleCase(item.status||'info'))}</em></button>`).join('')||'<div class="empty-row">Platform activity will appear as operations are completed.</div>';
  activity?.querySelectorAll('[data-activity-kind]').forEach(button=>button.addEventListener('click',async()=>{const kind=button.dataset.activityKind;if(kind==='audit'&&button.dataset.activityReference){openAuditPage();return openAudit(button.dataset.activityReference)}if(kind==='rule'||kind==='contract')return navigateToPage('rules');if(kind==='dataset')return navigateToPage('datasets')}));
  const alerts=document.querySelector('#overviewAlertList');if(alerts)alerts.innerHTML=(payload.alerts||[]).map(alert=>`<button class="overview-list-item alert-item" data-overview-alert="${alert.id}"><i class="${overviewStatusClass(alert.severity)}">${alert.severity==='critical'?'\u25b3':'!'}</i><span><strong>${escapeHtml(alert.title)}</strong><small>${alert.detected_at?new Date(alert.detected_at).toLocaleString():'\u2014'}</small></span><em class="${overviewStatusClass(alert.severity)}">${escapeHtml(titleCase(alert.severity))}</em></button>`).join('')||'<div class="empty-row">No active alerts in this workspace.</div>';
  alerts?.querySelectorAll('[data-overview-alert]').forEach(button=>button.addEventListener('click',()=>navigateToPage('alerts')));
  const summaryItems=[['Datasets',platform.datasets,'\u25a4'],['Dataset Versions',platform.versions,'\u25a5'],['Audits This Week',platform.audits_this_week,'\u25b6'],['Success Rate',`${platform.success_rate||0}%`,'\u2713'],['Active Users',platform.active_users,'\u2659'],['Rules',platform.rules,'\u25a7'],['Contracts',platform.contracts,'\u25a8'],['Connectors',platform.connectors,'\u2318'],['Reports Generated',platform.reports,'\u25a5'],['Action Points',platform.action_points,'\u2606']];
  const summary=document.querySelector('#overviewPlatformSummary');if(summary)summary.innerHTML=summaryItems.map(([label,value,icon])=>`<article><i>${icon}</i><span>${label}</span><strong>${value??0}</strong></article>`).join('');
  const upcoming=document.querySelector('#overviewUpcomingAudits');if(upcoming)upcoming.innerHTML=(payload.upcoming||[]).map(run=>`<button class="overview-upcoming-item" data-overview-schedule="${run.id}"><i>\u25b6</i><span><strong>${escapeHtml(run.name)}</strong><small>${run.next_run_at?new Date(run.next_run_at).toLocaleString():'\u2014'} \u00b7 ${escapeHtml(titleCase(run.frequency))}</small></span><em>${overviewRelativeTime(run.next_run_at)}</em></button>`).join('')||'<div class="empty-row">No active audit schedules.</div>';
  upcoming?.querySelectorAll('[data-overview-schedule]').forEach(button=>button.addEventListener('click',()=>navigateToPage('schedules')));
}


bindDashboardShell();


const datasetState = { rows: [], selectedId: null, selectedRow: null, environment: "all", search: "", page: 1, pageSize: 10 };

function bindDatasetWorkspace() {
  document.querySelector("#addDatasetButton")?.addEventListener("click", () => document.querySelector("#datasetCreatePanel")?.classList.remove("hidden"));
  document.querySelector("#closeDatasetCreate")?.addEventListener("click", closeDatasetCreate);
  document.querySelector("#cancelDatasetCreate")?.addEventListener("click", closeDatasetCreate);
  document.querySelector("#datasetCreateForm")?.addEventListener("submit", createDatasetRegistryEntry);
  document.querySelector("#datasetImportButton")?.addEventListener("click", () => document.querySelector("#datasetImportInput")?.click());
  document.querySelector("#datasetImportInput")?.addEventListener("change", importDatasetCsv);
  document.querySelector("#datasetVersionImportButton")?.addEventListener("click", () => document.querySelector("#datasetVersionImportInput")?.click());
  document.querySelector("#datasetVersionImportInput")?.addEventListener("change", importDatasetVersionCsv);
  document.querySelector("#refreshDatasetsButton")?.addEventListener("click", refreshDatasets);
  document.querySelector("#datasetSearchInput")?.addEventListener("input", event => { datasetState.search = event.target.value; datasetState.page = 1; renderDatasetRows(); });
  document.querySelectorAll("#datasetEnvironmentTabs [data-environment]").forEach(button => button.addEventListener("click", () => {
    document.querySelectorAll("#datasetEnvironmentTabs button").forEach(item => item.classList.remove("active"));
    button.classList.add("active"); datasetState.environment = button.dataset.environment; datasetState.page = 1; renderDatasetRows();
  }));
  document.querySelector("#datasetRowsPerPage")?.addEventListener("change", event => {
    datasetState.pageSize = Number(event.target.value) || 10;
    datasetState.page = 1;
    renderDatasetRows();
  });
  document.querySelector("#datasetPreviousPage")?.addEventListener("click", () => {
    if (datasetState.page > 1) { datasetState.page -= 1; renderDatasetRows(); }
  });
  document.querySelector("#datasetNextPage")?.addEventListener("click", () => {
    const totalPages = Math.max(1, Math.ceil(filteredDatasets().length / datasetState.pageSize));
    if (datasetState.page < totalPages) { datasetState.page += 1; renderDatasetRows(); }
  });
}

function openDatasetsPage() {
  hideAllPages();
  animatePage(document.querySelector("#datasetsPage"));
  authEls.datasetsNavButton?.classList.add("active");
  loadDatasets();
}

function closeDatasetCreate() { resetDatasetForm(); }

async function createDatasetRegistryEntry(event) {
  event.preventDefault(); setStatus("Registering dataset...");
  const payload = {
    name: document.querySelector("#datasetName").value.trim(), domain: document.querySelector("#datasetDomain").value.trim() || "General",
    owner_name: document.querySelector("#datasetOwner").value.trim() || state.currentUser?.full_name || "Workspace team",
    environment: document.querySelector("#datasetEnvironment").value, source_type: document.querySelector("#datasetSource").value.trim() || "CSV",
    labels: document.querySelector("#datasetLabels").value.split(",").map(value => value.trim()).filter(Boolean),
    description: document.querySelector("#datasetDescription").value.trim() || null,
  };
  const response = await fetch("/datasets", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  const body = await response.json().catch(()=>({}));
  if (!response.ok) { setStatus(body.detail || "Unable to register dataset."); return; }
  closeDatasetCreate(); setStatus("Dataset registered."); await loadDatasets(body.id);
}

function setDatasetImportStatus(message, tone = "info", busy = false) {
  const banner = document.querySelector("#datasetImportStatus");
  const button = document.querySelector("#datasetImportButton");
  if (button) {
    button.disabled = busy;
    button.textContent = busy ? "Importing\u2026" : "\u21e7 Import CSV";
  }
  if (!banner) return;
  banner.className = `dataset-import-status tone-${tone}`;
  banner.innerHTML = `${busy ? '<span class="dataset-import-spinner" aria-hidden="true"></span>' : ''}<span>${escapeHtml(message)}</span>`;
}


function showVersionImportResult(body) {
  const banner = document.querySelector("#datasetImportStatus");
  if (!banner) return;
  const created = body.audit_created_at ? new Date(body.audit_created_at).toLocaleString() : "Completed now";
  banner.className = "dataset-import-status tone-success version-import-result";
  banner.innerHTML = `
    <div class="version-import-result-copy">
      <span class="version-import-result-kicker">Version v${Number(body.version || 0)} imported</span>
      <strong>Automatic audit completed</strong>
      <span>${escapeHtml(body.source_filename || "Uploaded CSV")} \u00b7 ${escapeHtml(created)}</span>
    </div>
    <div class="version-import-result-metrics">
      <span><small>Score</small><strong>${Number(body.score ?? 0)}</strong></span>
      <span><small>Issues</small><strong>${Number(body.issue_count ?? 0)}</strong></span>
      <span><small>Rows</small><strong>${Number(body.row_count ?? 0).toLocaleString()}</strong></span>
      <span><small>Columns</small><strong>${Number(body.column_count ?? 0)}</strong></span>
    </div>
    <div class="version-import-result-actions">
      <button type="button" id="openImportedAuditButton">Open generated audit</button>
      <button type="button" class="secondary-button" id="openImportedVersionsButton">View version lineage</button>
      <button type="button" class="secondary-button" id="openImportedDriftButton">View detected drift</button>
    </div>`;
  document.querySelector("#openImportedAuditButton")?.addEventListener("click", async () => {
    navigateToPage("audit");
    await openAudit(body.audit_id);
  });
  document.querySelector("#openImportedVersionsButton")?.addEventListener("click", () => {
    versionWorkspaceState.pendingDatasetId = Number(body.dataset_id);
    navigateToPage("versions");
  });
  document.querySelector("#openImportedDriftButton")?.addEventListener("click", () => {
    driftState.pendingDatasetId = Number(body.dataset_id);
    navigateToPage("drift");
  });
}

async function importDatasetCsv(event) {
  const input = event.target;
  const file = input.files?.[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv") || !["text/csv","application/vnd.ms-excel",""] .includes(file.type)) {
    setDatasetImportStatus("Please choose a CSV file.", "error");
    input.value = "";
    return;
  }
  if (file.size === 0) { setDatasetImportStatus("The selected CSV file is empty.", "error"); input.value = ""; return; }
  if (file.size > 20 * 1024 * 1024) { setDatasetImportStatus("The CSV exceeds the 20 MB upload limit.", "error"); input.value = ""; return; }
  setDatasetImportStatus(`Importing and auditing ${file.name}. This may take a few seconds.`, "info", true);
  try {
    const form = new FormData();
    form.append("file", file);
    form.append("rules_json", "");
    const response = await fetch("/audits/upload", {method:"POST", body:form});
    const body = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Dataset import failed.");
    state.audit = body;
    await loadHistory();
    const datasetsResponse = await fetch("/datasets");
    const datasets = datasetsResponse.ok ? await datasetsResponse.json() : [];
    const imported = datasets.find(item => item.latest_audit_id === body.audit_id || item.name === body.dataset_name);
    await loadDatasets(imported?.id || null);
    setDatasetImportStatus(`${file.name} was imported, audited, and added to the registry.`, "success");
  } catch (error) {
    console.error("Dataset import failed", error);
    setDatasetImportStatus(error?.message || "Dataset import failed. Check the server terminal for details.", "error");
  } finally {
    input.value = "";
    const button = document.querySelector("#datasetImportButton");
    if (button) { button.disabled = false; button.textContent = "\u21e7 Import CSV"; }
  }
}


async function importDatasetVersionCsv(event) {
  const input = event.target;
  const file = input.files?.[0];
  const dataset = datasetState.selectedRow;
  if (!file || !dataset) { input.value = ""; return; }
  if (!file.name.toLowerCase().endsWith(".csv") || file.size === 0) {
    setDatasetImportStatus("Choose a non-empty CSV file for the new version.", "error");
    input.value = ""; return;
  }
  const button = document.querySelector("#datasetVersionImportButton");
  if (button) { button.disabled = true; button.textContent = "Importing version\u2026"; }
  setDatasetImportStatus(`Importing ${file.name} as a new version of ${dataset.name}.`, "info", true);
  try {
    const form = new FormData(); form.append("file", file);
    const response = await fetch(`/datasets/${dataset.id}/versions/import`, {method:"POST", body:form});
    const body = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(body.detail || "Version import failed.");
    await loadDatasets(dataset.id);
    showVersionImportResult(body);
  } catch (error) {
    setDatasetImportStatus(error.message || "Version import failed.", "error");
  } finally {
    input.value = "";
    if (button) { button.disabled = !datasetState.selectedId; button.textContent = "\u21bb Import new version"; }
  }
}

async function loadDatasets(preferredId = null) {
  const [rowsResponse, summaryResponse] = await Promise.all([fetch("/datasets"), fetch("/datasets/summary")]);
  if (!rowsResponse.ok) { setStatus("Unable to load datasets."); return; }
  datasetState.rows = await rowsResponse.json();
  const summary = summaryResponse.ok ? await summaryResponse.json() : {};
  setText("#datasetRegisteredMetric", summary.registered ?? datasetState.rows.length);
  setText("#datasetMonitoredMetric", summary.monitored ?? 0); setText("#datasetIssuesMetric", summary.active_issues ?? 0); setText("#datasetRecentMetric", summary.recently_updated ?? 0);
  renderDatasetRows();
  const target = preferredId || datasetState.selectedId || datasetState.rows[0]?.id;
  if (target) await selectDataset(Number(target)); else renderEmptyDatasetDetail();
}

function filteredDatasets() {
  const query = datasetState.search.toLowerCase().trim();
  return datasetState.rows.filter(row => (datasetState.environment === "all" || row.environment === datasetState.environment) &&
    (!query || [row.name,row.domain,row.owner_name,row.status].some(value => String(value||"").toLowerCase().includes(query))));
}

function datasetRegistryIcon() {
  return `<span class="dataset-registry-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><ellipse cx="12" cy="5" rx="7" ry="3"></ellipse><path d="M5 5v5c0 1.7 3.1 3 7 3s7-1.3 7-3V5"></path><path d="M5 10v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"></path><path d="M5 15v4c0 1.7 3.1 3 7 3s7-1.3 7-3v-4"></path></svg></span>`;
}

function datasetDeleteIcon() {
  return `<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"></path><path d="M9 7V4h6v3"></path><path d="M7 7l1 13h8l1-13"></path><path d="M10 11v5"></path><path d="M14 11v5"></path></svg>`;
}

function renderDatasetRows() {
  const holder = document.querySelector("#datasetRows"); if (!holder) return;
  const rows = filteredDatasets();
  const totalPages = Math.max(1, Math.ceil(rows.length / datasetState.pageSize));
  datasetState.page = Math.min(Math.max(1, datasetState.page), totalPages);
  const startIndex = (datasetState.page - 1) * datasetState.pageSize;
  const pageRows = rows.slice(startIndex, startIndex + datasetState.pageSize);
  holder.innerHTML = pageRows.length ? pageRows.map(row => `<div class="dataset-row ${row.id===datasetState.selectedId?'selected':''}" data-dataset-id="${row.id}" role="button" tabindex="0" aria-label="Open ${escapeHtml(row.name)}">
    <span class="dataset-cell-name">${datasetRegistryIcon()}<span class="dataset-name-stack"><strong>${escapeHtml(row.name)}</strong><small>${row.latest_version ? `Latest version: v${row.latest_version}${row.latest_source_filename ? ` \u00b7 ${escapeHtml(row.latest_source_filename)}` : ''}` : 'No imported version yet'}</small></span></span><span>${escapeHtml(row.domain)}</span><span>${escapeHtml(row.owner_name)}</span>
    <span><i class="fresh-dot"></i>${formatFreshness(row.updated_at)}</span><span>${row.quality_score == null ? '<i class="score-empty">\u2014</i>' : `<i class="dataset-score score-${scoreTone(row.quality_score)}">${row.quality_score}</i>`}</span>
    <span><i class="dataset-status status-${escapeHtml(row.status)}">${formatDatasetStatus(row.status)}</i></span><span>${new Date(row.updated_at).toLocaleDateString()}</span>
    <button type="button" class="dataset-delete-button" data-delete-dataset="${row.id}" aria-label="Delete ${escapeHtml(row.name)}" title="Delete dataset">${datasetDeleteIcon()}</button>
  </div>`).join("") : '<div class="empty-row">No datasets match the current filters.</div>';

  const summary = document.querySelector("#datasetPaginationSummary");
  if (summary) {
    const first = rows.length ? startIndex + 1 : 0;
    const last = Math.min(startIndex + pageRows.length, rows.length);
    summary.textContent = rows.length ? `Showing ${first}\u2013${last} of ${rows.length} datasets` : "Showing 0 datasets";
  }
  setText("#datasetPageIndicator", `${datasetState.page} / ${totalPages}`);
  const previous = document.querySelector("#datasetPreviousPage");
  const next = document.querySelector("#datasetNextPage");
  if (previous) previous.disabled = datasetState.page <= 1;
  if (next) next.disabled = datasetState.page >= totalPages;

  holder.querySelectorAll("[data-dataset-id]").forEach(row => {
    row.addEventListener("click", event => {
      if (event.target.closest("[data-delete-dataset]")) return;
      selectDataset(Number(row.dataset.datasetId));
    });
    row.addEventListener("keydown", event => {
      if ((event.key === "Enter" || event.key === " ") && !event.target.closest("[data-delete-dataset]")) {
        event.preventDefault(); selectDataset(Number(row.dataset.datasetId));
      }
    });
  });
  holder.querySelectorAll("[data-delete-dataset]").forEach(button => button.addEventListener("click", event => {
    event.stopPropagation(); deleteDataset(Number(button.dataset.deleteDataset));
  }));
}

async function deleteDataset(id) {
  const row = datasetState.rows.find(item => item.id === id);
  if (!row) return;
  if (!(await confirmAppAction({title:"Delete dataset?",description:`Delete ${row.name}? This removes it from the dataset registry.`,confirmLabel:"Delete dataset",danger:true}))) return;
  const button = document.querySelector(`[data-delete-dataset="${id}"]`);
  if (button) { button.disabled = true; button.textContent = "\u2026"; }
  try {
    const response = await fetch(`/datasets/${id}`, { method: "DELETE" });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Unable to delete dataset.");
    }
    const wasSelected = datasetState.selectedId === id;
    datasetState.rows = datasetState.rows.filter(item => item.id !== id);
    if (wasSelected) { datasetState.selectedId = null; datasetState.selectedRow = null; }
    await loadDatasets(wasSelected ? null : datasetState.selectedId);
    setDatasetImportStatus(`${row.name} was deleted from the registry.`, "success");
  } catch (error) {
    if (button) { button.disabled = false; button.innerHTML = datasetDeleteIcon(); }
    setDatasetImportStatus(error.message || "Unable to delete dataset.", "error");
  }
}

async function selectDataset(id) {
  const response = await fetch(`/datasets/${id}`); if (!response.ok) return;
  const row = await response.json(); datasetState.selectedId = id; datasetState.selectedRow = row; renderDatasetRows();
  const versionButton = document.querySelector("#datasetVersionImportButton"); if (versionButton) versionButton.disabled = false;
  setText("#datasetDetailName", row.name); const status = document.querySelector("#datasetDetailStatus"); status.textContent = formatDatasetStatus(row.status); status.className = `status-badge status-${row.status}`;
  document.querySelector("#datasetDetailBody").innerHTML = `<div class="dataset-facts"><div><span>Records</span><strong>${Number(row.record_count||0).toLocaleString()}</strong></div><div><span>Schema columns</span><strong>${row.column_count||0}</strong></div><div><span>Domain</span><strong>${escapeHtml(row.domain||'General')}</strong></div><div><span>Owner</span><strong>${escapeHtml(row.owner_name)}</strong></div><div><span>Environment</span><strong>${escapeHtml(row.environment)}</strong></div><div><span>Source type</span><strong>${escapeHtml(row.source_type)}</strong></div><div><span>Quality score</span><strong>${row.quality_score==null?'\u2014':row.quality_score}</strong></div><div><span>Active issues</span><strong>${row.issue_count||0}</strong></div><div><span>Latest version</span><strong>${row.latest_version ? `v${row.latest_version}` : '\u2014'}</strong></div><div><span>Latest source file</span><strong>${escapeHtml(row.latest_source_filename || '\u2014')}</strong></div></div>${row.description ? `<p class="dataset-description">${escapeHtml(row.description)}</p>` : '<p class="dataset-description muted">No description added.</p>'}`;
  await renderDatasetPreview(row.id);
  renderDatasetLabels(row);
  const labelInput = document.querySelector("#datasetLabelInput");
  const labelButton = document.querySelector("#datasetLabelAddButton");
  if (labelInput) labelInput.disabled = false;
  if (labelButton) labelButton.disabled = false;
  const actions = [];
  if (!row.latest_audit_id) actions.push(["Run a new audit","Validate this dataset with a reliability assessment","audit"]);
  if (row.issue_count > 0) actions.push(["Review quality issues",`${row.issue_count} issues need attention`,"issues"]);
  actions.push(["Edit dataset details","Keep ownership, labels, and lifecycle current","edit"]);
  document.querySelector("#datasetActions").innerHTML = actions.map(([title,copy,action])=>`<button class="dataset-recommendation" data-dataset-action="${action}"><i>${action==='audit'?'\u25b6':action==='issues'?'\u2315':'\u270e'}</i><span><strong>${title}</strong><small>${copy}</small></span><b>\u203a</b></button>`).join("");
  document.querySelectorAll("[data-dataset-action]").forEach(button => button.addEventListener("click", () => handleDatasetAction(button.dataset.datasetAction, row)));
}


function normalizeDatasetLabels(value) {
  if (Array.isArray(value)) return value.map(label => String(label).trim()).filter(Boolean);
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed.map(label => String(label).trim()).filter(Boolean);
    } catch (_) {
      return value.split(",").map(label => label.trim()).filter(Boolean);
    }
  }
  return [];
}

function renderDatasetLabels(row) {
  const holder = document.querySelector("#datasetLabelList");
  if (!holder) return;
  const labels = normalizeDatasetLabels(row?.labels);
  holder.innerHTML = labels.length
    ? labels.map(label => `<button type="button" class="dataset-label-chip" data-remove-label="${escapeHtml(label)}" title="Remove ${escapeHtml(label)}"><span class="dataset-label-text">${escapeHtml(label)}</span><span class="dataset-label-remove" aria-hidden="true">\u00d7</span></button>`).join("")
    : '<span class="muted">No labels assigned</span>';
  holder.querySelectorAll("[data-remove-label]").forEach(button => button.addEventListener("click", () => updateDatasetLabels(labels.filter(label => label !== button.dataset.removeLabel))));
}

async function updateDatasetLabels(labels) {
  if (!datasetState.selectedId) return;
  const normalized = [...new Set(labels.map(label => String(label).trim()).filter(Boolean))];
  const labelButton = document.querySelector("#datasetLabelAddButton");
  if (labelButton) labelButton.disabled = true;
  try {
    const response = await fetch(`/datasets/${datasetState.selectedId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labels: normalized }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Unable to update dataset labels.");
    const optimistic = { ...datasetState.selectedRow, ...body, labels: normalized };
    datasetState.selectedRow = optimistic;
    datasetState.rows = datasetState.rows.map(row => row.id === optimistic.id ? { ...row, ...optimistic } : row);
    renderDatasetLabels(optimistic);
    renderDatasetRows();
    await selectDataset(optimistic.id);
    setDatasetImportStatus("Dataset labels updated.", "success");
  } catch (error) {
    setDatasetImportStatus(error.message || "Unable to update dataset labels.", "error");
  } finally {
    if (labelButton) labelButton.disabled = false;
  }
}

async function addDatasetLabel(event) {
  event.preventDefault();
  if (!datasetState.selectedRow) return;
  const input = document.querySelector("#datasetLabelInput");
  const value = input?.value.trim();
  if (!value) return;
  const existing = normalizeDatasetLabels(datasetState.selectedRow.labels);
  await updateDatasetLabels([...existing, value]);
  if (input) input.value = "";
}

async function renderDatasetPreview(datasetId) {
  const holder = document.querySelector("#datasetPreview");
  if (!holder) return;
  holder.innerHTML = '<div class="ui-loading-state"><span class="ui-spinner"></span><span>Loading schema\u2026</span></div>';
  try {
    const response = await fetch(`/datasets/${datasetId}/preview?limit=8`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Unable to load dataset preview.");
    if (!data.available) { holder.innerHTML = `<div class="dataset-preview-empty">${escapeHtml(data.message || "Preview unavailable.")}</div>`; return; }
    const columns = data.columns || [];
    holder.innerHTML = `<div class="preview-summary"><span><strong>${Number(data.row_count||0).toLocaleString()}</strong> rows</span><span><strong>${data.column_count||0}</strong> columns</span><span><strong>${data.duplicate_row_count||0}</strong> duplicate rows</span></div>
      <div class="schema-scroll"><div class="schema-table schema-intelligence-table"><div class="schema-head"><span>Column</span><span>Type</span><span>Missing</span><span>Cardinality</span><span>Risk</span><span>Examples</span></div>${columns.map(column=>`<div class="schema-row"><strong>${escapeHtml(column.name)}</strong><span class="type-pill">${escapeHtml(column.inferred_type)}</span><span>${column.missing_count} (${Math.round(Number(column.missing_rate||0)*100)}%)</span><span>${escapeHtml(column.cardinality||'unknown')}</span><span><i class="column-risk risk-${escapeHtml(column.risk_level||'low')}" title="${escapeHtml((column.signals||[]).join('; ')||'No material risks detected')}">${escapeHtml(column.risk_level||'low')}</i></span><span class="example-values">${(column.sample_values||[]).slice(0,3).map(escapeHtml).join(', ') || '\u2014'}</span></div>`).join('')}</div></div>`;
  } catch (error) { holder.innerHTML = `<div class="dataset-preview-error">${escapeHtml(error.message || "Unable to load preview.")}</div>`; }
}

async function refreshDatasets() {
  const button = document.querySelector("#refreshDatasetsButton");
  const original = button?.textContent || "Refresh \u2192";
  if (button) { button.disabled = true; button.textContent = "Refreshing\u2026"; }
  try { await loadDatasets(datasetState.selectedId); setDatasetImportStatus("Dataset registry refreshed.", "success"); }
  finally { if (button) { button.disabled = false; button.textContent = original; } }
}


async function handleDatasetAction(action, row) {
  if (action === "edit") { openDatasetEditor(row); return; }
  if (!["audit", "issues"].includes(action)) return;

  const url = new URL(window.location.href);
  url.searchParams.set("page", "audit");
  url.searchParams.set("dataset", String(row.id));
  url.searchParams.set("dataset_name", row.name);
  if (row.latest_audit_id) url.searchParams.set("audit", row.latest_audit_id);
  else url.searchParams.delete("audit");
  if (action === "issues") url.searchParams.set("tab", "issues");
  else url.searchParams.delete("tab");
  history.pushState({ page: "audit", dataset: row.id, audit: row.latest_audit_id || null }, "", url);

  openAuditPage();
  if (!row.latest_audit_id) {
    setStatus(`${row.name} has no completed audit yet.`);
    return;
  }
  await openAudit(row.latest_audit_id);
  if (action === "issues") {
    auditV2.search.value = "";
    renderAuditIssuesV2();
    document.querySelector("#auditV2IssueBody")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function openDatasetEditor(row) {
  const panel = document.querySelector("#datasetCreatePanel");
  panel?.classList.remove("hidden");
  panel?.scrollIntoView({ behavior: "smooth", block: "start" });
  const heading = panel?.querySelector("h2");
  const eyebrow = panel?.querySelector(".eyebrow");
  if (heading) heading.textContent = "Edit Dataset Details";
  if (eyebrow) eyebrow.textContent = "Dataset metadata";
  document.querySelector("#datasetName").value=row.name; document.querySelector("#datasetName").disabled=false;
  document.querySelector("#datasetDomain").value=row.domain||"General"; document.querySelector("#datasetOwner").value=row.owner_name||"";
  document.querySelector("#datasetEnvironment").value=row.environment||"production"; document.querySelector("#datasetSource").value=row.source_type||"CSV";
  document.querySelector("#datasetLabels").value=(row.labels||[]).join(", "); document.querySelector("#datasetDescription").value=row.description||"";
  const form=document.querySelector("#datasetCreateForm"); form.dataset.editId=row.id; form.querySelector('button[type="submit"]').textContent="Save changes";
}

async function createOrUpdateDataset(event) {
  event.preventDefault(); const form=event.currentTarget; const editId=form.dataset.editId;
  if (!editId) return createDatasetRegistryEntry(event);
  const payload={name:document.querySelector("#datasetName").value.trim(),domain:document.querySelector("#datasetDomain").value.trim()||"General",owner_name:document.querySelector("#datasetOwner").value.trim()||"Workspace team",environment:document.querySelector("#datasetEnvironment").value,source_type:document.querySelector("#datasetSource").value.trim()||"CSV",description:document.querySelector("#datasetDescription").value.trim()||null,labels:document.querySelector("#datasetLabels").value.split(",").map(v=>v.trim()).filter(Boolean)};
  const response=await fetch(`/datasets/${editId}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); const body=await response.json().catch(()=>({}));
  if(!response.ok){setStatus(body.detail||"Unable to update dataset.");return;} resetDatasetForm(); setStatus("Dataset updated."); await loadDatasets(body.id);
}

function resetDatasetForm(){ const form=document.querySelector("#datasetCreateForm"); form.reset(); delete form.dataset.editId; document.querySelector("#datasetName").disabled=false; form.querySelector('button[type="submit"]').textContent="Register dataset"; const panel=document.querySelector("#datasetCreatePanel"); const heading=panel?.querySelector("h2"); const eyebrow=panel?.querySelector(".eyebrow"); if(heading)heading.textContent="Add Dataset"; if(eyebrow)eyebrow.textContent="New registry entry"; panel?.classList.add("hidden"); }
function renderEmptyDatasetDetail(){ setText("#datasetDetailName","Choose a dataset"); setText("#datasetDetailStatus","\u2014"); document.querySelector("#datasetDetailBody").innerHTML='Select a dataset from the registry to inspect its profile and audit history.'; }
function formatFreshness(value){ const hours=Math.max(0,Math.floor((Date.now()-new Date(value).getTime())/3600000)); return hours<1?'Just now':hours<24?`${hours}h ago`:`${Math.floor(hours/24)}d ago`; }
function scoreTone(score){ return score>=80?'good':score>=60?'warn':'bad'; }
function formatDatasetStatus(status){ return ({registered:'Registered',healthy:'Healthy',warning:'Warning',review_needed:'Review Needed',archived:'Archived'})[status]||status; }

bindDatasetWorkspace();
const datasetForm=document.querySelector("#datasetCreateForm"); if(datasetForm){datasetForm.removeEventListener("submit",createDatasetRegistryEntry);datasetForm.addEventListener("submit",createOrUpdateDataset);}


document.querySelector("#datasetLabelForm")?.addEventListener("submit", addDatasetLabel);

// Feature 10 \u2014 Audit Workspace Overhaul
const auditV2 = {
  dashboard: document.querySelector('#auditV2Dashboard'),
  empty: document.querySelector('#auditV2Empty'),
  dataset: document.querySelector('#auditDatasetSelect'),
  run: document.querySelector('#auditRunSelect'),
  severity: document.querySelector('#auditV2Severity'),
  category: document.querySelector('#auditV2Category'),
  search: document.querySelector('#auditV2Search'),
  issueBody: document.querySelector('#auditV2IssueBody'),
};
let auditSeverityChart = null;
let auditCategoryChart = null;


function bindAuditWorkspaceV2() {
  if (!auditV2.dashboard) return;
  document.querySelector('#auditRunButton')?.addEventListener('click', rerunSelectedAudit);
  document.querySelector('#auditV2UploadButton')?.addEventListener('click', () => els.fileInput.click());
  document.querySelector('#auditV2SampleButton')?.addEventListener('click', () => runAudit('/audits/sample', {method:'POST'}));
  document.querySelector('#auditExportButton')?.addEventListener('click', () => {
    if (!state.audit) return setStatus('Select an audit before exporting.');
    window.open(`/audits/${state.audit.audit_id}/report.html`, '_blank', 'noopener');
  });
  document.querySelector('#auditFullReportButton')?.addEventListener('click', () => {
    if (state.audit) window.open(`/audits/${state.audit.audit_id}/report.html`, '_blank', 'noopener');
  });
  document.querySelector('#auditCompareButton')?.addEventListener('click', compareCurrentWithPreviousV2);
  document.querySelector('#auditComparisonClose')?.addEventListener('click', () => document.querySelector('#auditComparisonPanel')?.classList.add('hidden'));
  document.querySelector('#remediationDeselectAll')?.addEventListener('click', () => { state.selectedActionIds.clear(); renderRemediation(); const s=document.querySelector('#remediationPreviewStatus'); if(s) s.textContent='Not previewed'; });
  document.querySelector('#remediationBackToAudit')?.addEventListener('click', () => navigateToPage('audit'));
  document.querySelector('#remediationSelectAudit')?.addEventListener('click', () => navigateToPage('audit'));
  document.querySelector('#auditRemediationButton')?.addEventListener('click', () => navigateToPage('remediation'));
  auditV2.dataset?.addEventListener('change', () => populateAuditRunSelectV2(auditV2.dataset.value, true));
  auditV2.run?.addEventListener('change', () => auditV2.run.value && openAudit(auditV2.run.value));
  auditV2.severity?.addEventListener('change', renderAuditIssuesV2);
  auditV2.category?.addEventListener('change', renderAuditIssuesV2);
  auditV2.search?.addEventListener('input', renderAuditIssuesV2);
  document.querySelector('#auditClearFilters')?.addEventListener('click', () => {
    auditV2.severity.value = 'all'; auditV2.category.value = 'all'; auditV2.search.value = ''; renderAuditIssuesV2();
  });
}


async function rerunSelectedAudit() {
  if (!state.audit?.audit_id) {
    setStatus("Select a dataset and completed audit before rerunning.");
    return;
  }
  const rerunUrl = `/audits/${state.audit.audit_id}/rerun`;
  const sourceAuditId = state.audit.audit_id;
  const sourceDatasetName = state.audit.dataset_name;
  const button = document.querySelector('#auditRunButton');
  if (button) { button.disabled = true; button.textContent = 'Rerunning\u2026'; }
  try {
    const payload = await runAudit(
      rerunUrl,
      { method: 'POST' },
      `Rerunning audit for ${sourceDatasetName}\u2026`
    );
    if (!payload?.audit_id) return;

    await loadHistory();
    await openAudit(payload.audit_id);
    populateAuditSelectorsV2();
    if (auditV2.dataset) auditV2.dataset.value = payload.dataset_name;
    populateAuditRunSelectV2(payload.dataset_name, false);
    if (auditV2.run) auditV2.run.value = payload.audit_id;

    const url = new URL(window.location.href);
    url.searchParams.set('page', 'audit');
    url.searchParams.set('audit', payload.audit_id);
    url.searchParams.set('dataset_name', payload.dataset_name);
    history.replaceState({ page: 'audit', audit: payload.audit_id }, '', url);
    setStatus(`New audit run completed for ${payload.dataset_name}.`);
  } finally {
    if (button) { button.disabled = false; button.textContent = '\u25b7 Run Audit'; }
  }
}

function populateAuditSelectorsV2() {
  if (!auditV2.dataset) return;
  const names = [...new Set(state.history.map(item => item.dataset_name))];
  const selected = state.audit?.dataset_name || auditV2.dataset.value || names[0] || '';
  auditV2.dataset.innerHTML = names.map(name => `<option value="${escapeHtml(name)}" ${name === selected ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('');
  populateAuditRunSelectV2(selected, false);
}

function populateAuditRunSelectV2(datasetName, openLatest) {
  if (!auditV2.run) return;
  const runs = state.history.filter(item => item.dataset_name === datasetName);
  auditV2.run.innerHTML = runs.map(item => `<option value="${escapeHtml(item.audit_id)}" ${state.audit?.audit_id === item.audit_id ? 'selected' : ''}>${formatDateTime(item.created_at)} EAT \u00b7 ${item.score}/100</option>`).join('');
  if (openLatest && runs[0]) openAudit(runs[0].audit_id);
}

function renderAuditWorkspaceV2(audit) {
  if (!auditV2.dashboard) return;
  auditV2.empty.classList.add('hidden'); auditV2.dashboard.classList.remove('hidden');
  populateAuditSelectorsV2();
  const activeIssues = activeAuditIssuesV2(audit);
  const counts = severityCountsV2(activeIssues);
  setText('#auditV2Score', audit.score.overall); setText('#auditV2Risk', `${capitalizeV2(audit.summary.risk_level)} risk`);
  document.querySelector('#auditScoreRing')?.style.setProperty('--score', `${audit.score.overall}%`);
  setText('#auditV2Total', activeIssues.length); setText('#auditV2Critical', counts.critical + counts.high); setText('#auditV2Warning', counts.medium); setText('#auditV2Info', counts.low);
  setText('#auditV2Rules', audit.profile.column_count + Object.keys(audit.rule_config?.expected_types || {}).length + Object.keys(audit.rule_config?.allowed_values || {}).length);
  fillAuditFilterV2(auditV2.severity, [...new Set(audit.issues.map(i => i.severity))]);
  fillAuditFilterV2(auditV2.category, [...new Set(audit.issues.map(i => i.category))]);
  renderSeverityV2(activeIssues); renderCategoriesV2(activeIssues); renderImpactedV2(activeIssues); renderRunDetailsV2(audit); renderAuditIssuesV2(); updateAuditCompareActionV2();
}

function fillAuditFilterV2(select, values) {
  const current = select.value || 'all';
  select.innerHTML = '<option value="all">All</option>' + values.sort().map(v => `<option value="${escapeHtml(v)}">${escapeHtml(capitalizeV2(v))}</option>`).join('');
  select.value = values.includes(current) ? current : 'all';
}
function activeAuditIssuesV2(audit){return (audit?.issues||[]).filter(i=>!['fixed','resolved','ignored'].includes(i.status||'open'));}
function severityCountsV2(issues){return issues.reduce((a,i)=>(a[i.severity]=(a[i.severity]||0)+1,a),{critical:0,high:0,medium:0,low:0});}
function capitalizeV2(value){return String(value||'').replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());}
function setTextV2(selector,value){const el=document.querySelector(selector);if(el)el.textContent=value;}

function renderSeverityV2(issues) {
  const counts=severityCountsV2(issues);
  const values=[counts.critical+counts.high, counts.medium, counts.low];
  const canvas=document.querySelector('#auditSeverityChart');
  if(!canvas || typeof Chart==='undefined') return;
  if(auditSeverityChart) auditSeverityChart.destroy();
  auditSeverityChart=new Chart(canvas,{type:'doughnut',data:{labels:['Critical / High','Medium','Low'],datasets:[{data:values,backgroundColor:['#ef4444','#f59e0b','#4d9de0'],borderColor:'#ffffff',borderWidth:3,hoverOffset:8}]},options:{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{legend:{position:'right',labels:{usePointStyle:true,boxWidth:9,padding:14,font:{size:11}}},tooltip:{callbacks:{label:(context)=>{const total=context.dataset.data.reduce((a,b)=>a+b,0)||1;return ` ${context.label}: ${context.raw} (${Math.round(context.raw/total*100)}%)`;}}}},onClick:(_,elements)=>{if(!elements.length)return;const map=[['critical','high'],['medium'],['low']][elements[0].index];auditV2.severity.value=map.length===1?map[0]:'all';renderAuditIssuesV2();}}});
}
function renderCategoriesV2(issues){
  const counts={};issues.forEach(i=>counts[i.category]=(counts[i.category]||0)+1);
  const entries=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,6);
  const canvas=document.querySelector('#auditCategoryChart');
  if(!canvas || typeof Chart==='undefined') return;
  if(auditCategoryChart) auditCategoryChart.destroy();
  auditCategoryChart=new Chart(canvas,{type:'bar',data:{labels:entries.map(([name])=>capitalizeV2(name)),datasets:[{label:'Issues',data:entries.map(([,count])=>count),backgroundColor:['#ef4444','#f59e0b','#4d9de0','#8b6de9','#35b7a5','#95a3b3'],borderRadius:6,borderSkipped:false}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{displayColors:false}},scales:{x:{beginAtZero:true,ticks:{precision:0},grid:{color:'#edf1f4'}},y:{grid:{display:false}}},onClick:(_,elements)=>{if(!elements.length)return;auditV2.category.value=entries[elements[0].index][0];renderAuditIssuesV2();}}});
}
function renderImpactedV2(issues){const counts={};issues.forEach(i=>i.columns.forEach(c=>counts[c]=(counts[c]||0)+1));document.querySelector('#auditImpactedColumns').innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([c,n])=>`<div class="audit-impact-row"><span>${escapeHtml(c)}</span><b>${n}</b><b class="${n>=5?'high':n>=2?'medium':'low'}">${n>=5?'High':n>=2?'Medium':'Low'}</b></div>`).join('')||'<p class="muted">No impacted columns.</p>';}
function renderRunDetailsV2(audit){const sourceFile=audit.upload?.original_filename||audit.dataset_name||'--';const version=audit.dataset_version?`v${audit.dataset_version}`:'--';const details=[['Run ID',audit.audit_id.slice(0,16)],['Started',`${formatDateTime(audit.created_at)} EAT`],['Dataset version',version],['Source file',sourceFile],['Rows scanned',audit.profile.row_count.toLocaleString()],['Columns scanned',audit.profile.column_count],['Duplicate rows',audit.profile.duplicate_row_count],['Status','Completed']];document.querySelector('#auditRunDetails').innerHTML=details.map(([l,v])=>`<div><span>${l}</span><b title="${escapeHtml(String(v))}">${escapeHtml(String(v))}</b></div>`).join('');}

function filteredAuditIssuesV2(){if(!state.audit)return[];const sev=auditV2.severity?.value||'all',cat=auditV2.category?.value||'all',q=(auditV2.search?.value||'').toLowerCase();return state.audit.issues.filter(i=>(sev==='all'||i.severity===sev)&&(cat==='all'||i.category===cat)&&(!q||`${i.title} ${i.detail} ${i.columns.join(' ')}`.toLowerCase().includes(q)));}
function renderAuditIssuesV2(){if(!state.audit||!auditV2.issueBody)return;const issues=filteredAuditIssuesV2();setTextV2('#auditVisibleCount',`${issues.length} issue${issues.length===1?'':'s'}`);auditV2.issueBody.innerHTML=issues.map(i=>`<tr data-v2-issue="${escapeHtml(i.id)}" class="${state.selectedIssueId===i.id?'selected':''}"><td><span class="severity-pill ${escapeHtml(i.severity)}">${escapeHtml(capitalizeV2(i.severity))}</span></td><td>${escapeHtml(capitalizeV2(i.category))}</td><td class="audit-wrap-cell"><b>${escapeHtml(i.title)}</b></td><td class="audit-wrap-cell">${escapeHtml(i.columns.join(', ')||'Dataset')}</td><td class="audit-wrap-cell">${escapeHtml(i.detail)}</td><td>${i.affected_rows.toLocaleString()}</td><td>${(i.affected_rate*100).toFixed(1)}%</td><td><select data-v2-status="${escapeHtml(i.id)}">${statusOptions(i.status||'open')}</select></td></tr>`).join('')||'<tr><td colspan="8" class="empty-cell">No issues match the current filters.</td></tr>';
  document.querySelectorAll('[data-v2-issue]').forEach(row=>row.addEventListener('click',e=>{if(e.target.closest('select'))return;state.selectedIssueId=row.dataset.v2Issue;renderAuditIssuesV2();renderSelectedIssueV2();}));
  document.querySelectorAll('[data-v2-status]').forEach(select=>select.addEventListener('change',()=>updateIssueStatusV2(select.dataset.v2Status,select.value)));
  renderSelectedIssueV2();
}

function issueEvidenceHtmlV2(issue){
  const examples=Array.isArray(issue?.examples)?issue.examples.slice(0,3):[];
  if(!examples.length)return '<p>No row-level examples were captured for this finding.</p>';
  return `<div class="issue-evidence-list">${examples.map(example=>`<div class="issue-evidence-item"><code>${escapeHtml(JSON.stringify(example,null,2))}</code></div>`).join('')}</div>`;
}
function renderGeneralIssueIntelligenceV2(issue){
  if(!issue)return '';
  const columns=(issue.columns||[]).join(', ')||'Dataset-level';
  const confidence=Math.round(Number(issue.confidence||0)*100);
  return `<section class="issue-intelligence-panel">
    <div class="issue-intelligence-heading"><div><p class="eyebrow">Issue intelligence</p><h4>Evidence and recommended response</h4></div><span class="issue-confidence-badge">${confidence}% confidence</span></div>
    <dl class="issue-intelligence-meta">
      <div><dt>Category</dt><dd>${escapeHtml(capitalizeV2(issue.category))}</dd></div>
      <div><dt>Severity</dt><dd>${escapeHtml(capitalizeV2(issue.severity))}</dd></div>
      <div><dt>Affected data</dt><dd>${Number(issue.affected_rows||0).toLocaleString()} rows \u00b7 ${(Number(issue.affected_rate||0)*100).toFixed(1)}%</dd></div>
      <div><dt>Columns</dt><dd>${escapeHtml(columns)}</dd></div>
    </dl>
    <div class="issue-intelligence-section"><b>Business impact</b><p>${escapeHtml(businessImpact(issue))}</p></div>
    <div class="issue-intelligence-section"><b>Likely root cause</b><p>${escapeHtml(rootCause(issue))}</p></div>
    <div class="issue-intelligence-section"><b>Observed evidence</b>${issueEvidenceHtmlV2(issue)}</div>
    <div class="issue-intelligence-section issue-recommendation-box"><b>Recommended action</b><p>${escapeHtml(issue.recommendation||'Investigate and correct the affected records, then rerun validation.')}</p></div>
  </section>`;
}

function privacyIntelligenceForIssueV2(issue){
  if(!issue || issue.category!=='privacy' || !state.audit?.profile?.columns) return [];
  const selected=new Set(issue.columns||[]);
  return state.audit.profile.columns
    .filter(column=>selected.has(column.name) && column.privacy_classification)
    .map(column=>({
      column:column.name,
      classification:column.privacy_classification,
      sensitivity:column.sensitivity||'unknown',
      confidence:Number(column.privacy_confidence||0),
      reasons:Array.isArray(column.privacy_reasons)?column.privacy_reasons:[],
      recommendation:column.masking_recommendation||issue.recommendation
    }));
}
function renderPrivacyIntelligenceV2(issue){
  const findings=privacyIntelligenceForIssueV2(issue);
  if(!findings.length) return '';
  return `<section class="privacy-intelligence-panel">
    <div class="privacy-intelligence-heading"><div><p class="eyebrow">Privacy intelligence</p><h4>${findings.length} sensitive column${findings.length===1?'':'s'}</h4></div><span class="privacy-control-badge">Control required</span></div>
    <div class="privacy-finding-list">${findings.map(item=>`<article class="privacy-finding-card">
      <div class="privacy-finding-title"><b>${escapeHtml(item.column)}</b><span class="privacy-sensitivity ${escapeHtml(item.sensitivity)}">${escapeHtml(capitalizeV2(item.sensitivity))}</span></div>
      <dl class="privacy-finding-meta"><div><dt>Classification</dt><dd>${escapeHtml(capitalizeV2(item.classification))}</dd></div><div><dt>Confidence</dt><dd>${Math.round(item.confidence*100)}%</dd></div></dl>
      <div class="privacy-finding-copy"><b>Why it was detected</b><ul>${item.reasons.map(reason=>`<li>${escapeHtml(reason)}</li>`).join('')||'<li>Column metadata indicates sensitive information.</li>'}</ul></div>
      <div class="privacy-recommendation"><b>Protection guidance</b><p>${escapeHtml(item.recommendation)}</p></div>
    </article>`).join('')}</div>
    <p class="privacy-control-note">Record the privacy control implemented and its validation evidence below before resolving this finding.</p>
  </section>`;
}
function renderSelectedIssueV2(){
  const target=document.querySelector('#auditSelectedIssue');
  const issue=state.audit?.issues.find(i=>i.id===state.selectedIssueId);
  const isPrivacy=issue?.category==='privacy';
  target.innerHTML=issue?`<p class="eyebrow">Selected issue</p><h3>${escapeHtml(issue.title)}</h3><p>${escapeHtml(issue.detail)}</p>
    ${renderGeneralIssueIntelligenceV2(issue)}
    ${renderPrivacyIntelligenceV2(issue)}
    <div class="issue-lifecycle-grid">
      <label>Status<select id="issueLifecycleStatus">${statusOptions(issue.status||'open')}</select></label>
      <label>Severity<select id="issueLifecycleSeverity">${['low','medium','high','critical'].map(v=>`<option value="${v}" ${v===issue.severity?'selected':''}>${capitalizeV2(v)}</option>`).join('')}</select></label>
      <label>Owner<input id="issueLifecycleOwner" value="${escapeHtml(issue.owner||'')}" placeholder="Assign an owner"></label>
      <label>Due date<input id="issueLifecycleDueDate" type="date" value="${escapeHtml(issue.due_date||'')}"></label>
    </div>
    <label class="issue-lifecycle-field">${isPrivacy?'Implemented privacy control / resolution note':'Investigation / resolution note'}<textarea id="issueLifecycleNote" rows="3" placeholder="${isPrivacy?'Describe masking, tokenization, encryption, access restriction, or another implemented control':'Record findings, decisions, or resolution details'}">${escapeHtml(issue.resolution_note||'')}</textarea></label>
    <label class="issue-lifecycle-field">${isPrivacy?'Privacy control validation evidence':'Resolution evidence'}<textarea id="issueLifecycleEvidence" rows="2" placeholder="${isPrivacy?'Add validation results, configuration reference, ticket, or policy evidence':'Add validation evidence or a reference'}">${escapeHtml(issue.resolution_evidence||'')}</textarea></label>
    <div class="issue-lifecycle-actions"><button id="saveIssueLifecycleButton" class="secondary-button">Save issue</button>${!['fixed','resolved'].includes(issue.status)?`<button id="applyAuditRecommendationButton" class="apply-recommendation-button">${isPrivacy?'Apply Privacy Control':'Apply Recommendation'}</button>`:'<span class="status-badge">Resolved</span>'}</div>
    <form id="issueCommentForm" class="issue-comment-form"><input id="issueCommentInput" placeholder="Add investigation comment" required><button>Add note</button></form>
    <div id="issueActivityTimeline" class="issue-activity-timeline"><p class="muted">Loading activity\u2026</p></div>`:'<p class="muted">Select an issue to inspect and manage its lifecycle.</p>';
  document.querySelector('#applyAuditRecommendationButton')?.addEventListener('click',applySelectedRecommendationV2);
  document.querySelector('#saveIssueLifecycleButton')?.addEventListener('click',saveSelectedIssueLifecycleV2);
  document.querySelector('#issueCommentForm')?.addEventListener('submit',addIssueCommentV2);
  if(issue) loadIssueLifecycleV2();
}
async function saveSelectedIssueLifecycleV2(){
  if(!state.audit||!state.selectedIssueId)return;
  const payload={status:document.querySelector('#issueLifecycleStatus').value,severity:document.querySelector('#issueLifecycleSeverity').value,owner:document.querySelector('#issueLifecycleOwner').value.trim()||null,due_date:document.querySelector('#issueLifecycleDueDate').value||null,resolution_note:document.querySelector('#issueLifecycleNote').value.trim()||null,resolution_evidence:document.querySelector('#issueLifecycleEvidence').value.trim()||null};
  const response=await fetch(`/audits/${state.audit.audit_id}/issues/${state.selectedIssueId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok){setStatus(data.detail||'Unable to update issue.');return;}state.audit=data;renderAudit(state.audit);renderAuditWorkspaceV2(state.audit);setStatus('Issue lifecycle updated.');
}
async function addIssueCommentV2(event){event.preventDefault();const input=document.querySelector('#issueCommentInput');const body=input.value.trim();if(!body||!state.audit||!state.selectedIssueId)return;const response=await fetch(`/audits/${state.audit.audit_id}/issues/${state.selectedIssueId}/comments`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body})});const data=await response.json();if(!response.ok){setStatus(data.detail||'Unable to add note.');return;}input.value='';renderIssueActivityV2(data.activities);setStatus('Investigation note added.');}
async function loadIssueLifecycleV2(){if(!state.audit||!state.selectedIssueId)return;const response=await fetch(`/audits/${state.audit.audit_id}/issues/${state.selectedIssueId}/lifecycle`);if(!response.ok)return;const data=await response.json();renderIssueActivityV2(data.activities||[]);}
function renderIssueActivityV2(activities){const target=document.querySelector('#issueActivityTimeline');if(!target)return;target.innerHTML=activities.length?activities.map(item=>`<div class="issue-activity-item"><b>${escapeHtml(capitalizeV2(item.action))}</b><span>${escapeHtml(item.actor_name||'System')} \u00b7 ${formatDateTime(item.created_at)}</span><p>${escapeHtml(item.note||[item.field_name,item.previous_value&&`from ${item.previous_value}`,item.new_value&&`to ${item.new_value}`].filter(Boolean).join(' ')||'Issue updated')}</p></div>`).join(''):'<p class="muted">No lifecycle activity recorded yet.</p>';}

async function applySelectedRecommendationV2(){
  if(!state.audit||!state.selectedIssueId)return;
  const issue=state.audit.issues.find(item=>item.id===state.selectedIssueId);
  if(issue?.category==='privacy' && !(issue.resolution_note && issue.resolution_evidence)){
    setStatus('Record the implemented privacy control and validation evidence, then save the issue before applying it.');
    document.querySelector('#issueLifecycleNote')?.focus();
    return;
  }
  const button=document.querySelector('#applyAuditRecommendationButton');
  if(button){button.disabled=true;button.textContent='Applying recommendation\u2026';}
  try{
    const response=await fetch(`/audits/${state.audit.audit_id}/issues/${state.selectedIssueId}/apply-recommendation`,{method:'POST'});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.detail||'Unable to apply recommendation.');
    state.audit=payload.audit;
    renderAudit(state.audit);
    renderAuditWorkspaceV2(state.audit);
    setStatus(`Recommendation applied. Reliability score improved from ${payload.previous_score} to ${payload.updated_score}.`);
  }catch(error){setStatus(error.message||'Unable to apply recommendation.');renderSelectedIssueV2();}
}
async function updateIssueStatusV2(issueId,status){await updateIssueStatus(issueId,status);renderAuditWorkspaceV2(state.audit);}
function previousAuditForCurrentV2() {
  if (!state.audit) return null;
  const currentTime = new Date(state.audit.created_at || 0).getTime();
  return state.history
    .filter(item => item.dataset_name === state.audit.dataset_name && item.audit_id !== state.audit.audit_id)
    .filter(item => new Date(item.created_at || 0).getTime() < currentTime)
    .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))[0] || null;
}

function updateAuditCompareActionV2() {
  const button = document.querySelector('#auditCompareButton');
  if (!button) return;
  const previous = previousAuditForCurrentV2();
  button.hidden = false;
  button.disabled = !previous;
  button.title = previous
    ? `Compare with ${formatDateTime(previous.created_at)}`
    : 'Run this dataset again to create a previous audit for comparison.';
}

async function compareCurrentWithPreviousV2() {
  const panel = document.querySelector('#auditComparisonPanel');
  const content = document.querySelector('#auditComparisonContent');
  const title = document.querySelector('#auditComparisonTitle');
  if (!state.audit) {
    setStatus('Select an audit before comparing runs.');
    return;
  }
  const previous = previousAuditForCurrentV2();
  if (!previous) {
    updateAuditCompareActionV2();
    setStatus('No earlier run is available. Run the audit again, then compare the two runs.');
    return;
  }
  if (panel) panel.classList.remove('hidden');
  if (title) title.textContent = 'Comparing audit runs';
  if (content) content.innerHTML = '<div class="comparison-loading"><span class="spinner"></span><p>Loading comparison\u2026</p></div>';
  panel?.scrollIntoView({behavior:'smooth', block:'start'});
  setStatus('Comparing audit runs...');
  try {
    const response = await fetch(`/audits/compare/${previous.audit_id}/${state.audit.audit_id}`);
    const comparison = await parseResponse(response);
    if (!response.ok) throw new Error(responseErrorMessage(comparison, response.status));

    const newKeys = new Set((comparison.new_issues || []).map(comparisonIssueKeyV2));
    const persistentIssues = (state.audit.issues || []).filter(issue => !newKeys.has(comparisonIssueKeyV2(issue)));
    const persistentCount = persistentIssues.length;
    const scoreDelta = Number(comparison.score_delta || 0);
    const issueDelta = Number(comparison.issue_count_delta || 0);
    const resultTone = scoreDelta > 0 ? 'improved' : scoreDelta < 0 ? 'declined' : 'unchanged';
    const resultLabel = scoreDelta > 0 ? 'Improved' : scoreDelta < 0 ? 'Declined' : 'No change';

    if (title) title.textContent = `${scoreDelta >= 0 ? '+' : ''}${scoreDelta} reliability score change`;
    if (content) content.innerHTML = `
      <div class="comparison-summary-head">
        <div class="comparison-summary-copy">
          <span class="comparison-icon" aria-hidden="true">\u2696</span>
          <div><p class="eyebrow">Audit comparison</p><p>Comparing the current run with the immediately previous run for this dataset.</p></div>
        </div>
        <span class="comparison-result-badge ${resultTone}">${resultLabel}</span>
      </div>
      <div class="comparison-run-strip">
        ${renderComparisonRunCardV2('Previous run', previous.created_at, previous.audit_id, 'previous')}
        <div class="comparison-score-hero ${resultTone}">
          <strong>${scoreDelta >= 0 ? '+' : ''}${scoreDelta}</strong>
          <span>Reliability score change</span>
          <small>${scoreDelta > 0 ? '\u2197 Improvement' : scoreDelta < 0 ? '\u2198 Decline' : '\u2192 Stable'}</small>
        </div>
        ${renderComparisonRunCardV2('Current run', state.audit.created_at, state.audit.audit_id, 'current')}
      </div>
      <div class="comparison-kpi-grid comparison-kpi-grid-v2">
        ${renderComparisonMetricV2('Score change', `${scoreDelta >= 0 ? '+' : ''}${scoreDelta}`, resultLabel, resultTone)}
        ${renderComparisonMetricV2('Issue count change', `${issueDelta >= 0 ? '+' : ''}${issueDelta}`, issueDelta === 0 ? 'No change' : issueDelta < 0 ? 'Fewer issues' : 'More issues', issueDelta < 0 ? 'improved' : issueDelta > 0 ? 'declined' : 'unchanged')}
        ${renderComparisonMetricV2('New issues', comparison.new_issues?.length || 0, comparison.new_issues?.length ? 'Require review' : 'No new issues', comparison.new_issues?.length ? 'declined' : 'improved')}
        ${renderComparisonMetricV2('Resolved issues', comparison.resolved_issues?.length || 0, comparison.resolved_issues?.length ? 'Risk removed' : 'No resolved issues', comparison.resolved_issues?.length ? 'improved' : 'unchanged')}
        ${renderComparisonMetricV2('Persistent issues', persistentCount, persistentCount ? 'Still require attention' : 'No persistent issues', persistentCount ? 'warning' : 'improved')}
      </div>
      <div class="comparison-detail-grid comparison-detail-grid-v2">
        ${renderComparisonIssuePanelV2('New issues', comparison.new_issues, 'new')}
        ${renderComparisonIssuePanelV2('Resolved issues', comparison.resolved_issues, 'resolved')}
        ${renderPersistentIssuePanelV2(persistentIssues)}
        ${renderColumnImpactPanelV2(comparison.improved_columns || [], comparison.worsened_columns || [])}
      </div>`;
    setStatus('Audit comparison loaded.');
  } catch (error) {
    if (title) title.textContent = 'Comparison unavailable';
    if (content) content.innerHTML = `<div class="comparison-error"><strong>Unable to compare these runs.</strong><p>${escapeHtml(error.message || 'Unexpected comparison error.')}</p></div>`;
    setStatus(error.message || 'Unable to compare audit runs.');
  }
}
function comparisonIssueKeyV2(issue) {
  return `${issue.title || ''}|${(issue.columns || []).join(',')}`;
}
function renderComparisonRunCardV2(label, createdAt, auditId, type) {
  return `<article class="comparison-run-card ${type}"><span class="comparison-run-icon" aria-hidden="true">\u25a3</span><div><span>${label}</span><b>${escapeHtml(new Date(createdAt).toLocaleString())}</b><small title="${escapeHtml(auditId)}">${escapeHtml(auditId)}</small></div></article>`;
}
function renderComparisonMetricV2(label, value, note, tone='unchanged') {
  return `<article class="comparison-metric-card ${tone}"><span>${label}</span><b>${escapeHtml(String(value))}</b><small>${escapeHtml(note)}</small></article>`;
}
function renderComparisonIssuePanelV2(title, items = [], type='new') {
  const count = items.length;
  const emptyCopy = type === 'new' ? 'Great \u2014 no new issues were introduced.' : 'No issues were resolved in this comparison.';
  const icon = type === 'new' ? '+' : '\u2713';
  const rows = count ? items.slice(0, 4).map(item => `<li><span class="comparison-list-icon ${type}">${icon}</span><div><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.category)} \u00b7 ${escapeHtml(item.severity)}${item.columns?.length ? ` \u00b7 ${escapeHtml(item.columns.join(', '))}` : ''}</small></div></li>`).join('') : `<li class="comparison-empty-state"><span class="comparison-empty-icon">${type === 'new' ? '\u2713' : '\u25cb'}</span><p>${emptyCopy}</p></li>`;
  return `<section class="comparison-detail-card ${type}"><header><h3>${title} <span>(${count})</span></h3></header><ul class="comparison-list-v2">${rows}</ul>${count > 4 ? `<button class="comparison-text-action" type="button">View all ${count} ${title.toLowerCase()} \u2192</button>` : ''}</section>`;
}
function renderPersistentIssuePanelV2(items = []) {
  const rows = items.length ? items.slice(0, 4).map(issue => `<li><span class="comparison-list-icon persistent">!</span><div><b>${escapeHtml(issue.title)}</b><small>${escapeHtml(issue.category)} \u00b7 ${escapeHtml(issue.severity)}${issue.columns?.length ? ` \u00b7 ${escapeHtml(issue.columns.join(', '))}` : ''}</small></div></li>`).join('') : '<li class="comparison-empty-state"><span class="comparison-empty-icon">\u2713</span><p>No persistent issues remain.</p></li>';
  return `<section class="comparison-detail-card persistent"><header><h3>Persistent issues <span>(${items.length})</span></h3></header><ul class="comparison-list-v2">${rows}</ul>${items.length > 4 ? `<button class="comparison-text-action" type="button" data-action="filter-persistent">View all ${items.length} persistent issues \u2192</button>` : ''}</section>`;
}
function renderColumnImpactPanelV2(improved = [], worsened = []) {
  const renderItems = (items, tone, empty) => items.length ? `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : `<p>${empty}</p>`;
  return `<section class="comparison-detail-card column-impact"><header><h3>Column impact changes</h3></header><div class="comparison-column-change improved"><b>\u2191 Improved columns (${improved.length})</b>${renderItems(improved, 'improved', 'None')}</div><div class="comparison-column-change worsened"><b>\u2193 Worsened columns (${worsened.length})</b>${renderItems(worsened, 'worsened', 'None')}</div></section>`;
}
function renderComparisonIssueList(title, items = []) {
  const rows = items.length ? items.map(item => `<li><b>${escapeHtml(item.title)}</b><span>${escapeHtml(item.category)} \u00b7 ${escapeHtml(item.severity)}</span><small>${escapeHtml((item.columns || []).join(', ') || 'Dataset level')}</small></li>`).join('') : '<li class="muted">None</li>';
  return `<section><h3>${title}</h3><ul class="comparison-list">${rows}</ul></section>`;
}
function renderComparisonColumnList(title, items = []) {
  const rows = items.length ? items.map(item => `<li>${escapeHtml(item)}</li>`).join('') : '<li class="muted">None</li>';
  return `<section><h3>${title}</h3><ul class="comparison-list compact">${rows}</ul></section>`;
}
async function showRemediationSummaryV2(){if(!state.audit)return;const r=await fetch(`/audits/${state.audit.audit_id}/remediation`);const p=await r.json();document.querySelector('#auditSelectedIssue').innerHTML=`<p class="eyebrow">Remediation plan</p><h3>${p.actions.length} recommended actions</h3><p>${p.actions.slice(0,3).map(a=>escapeHtml(a.title)).join(' \u00b7 ')||'No remediation is required.'}</p>`;}

bindAuditWorkspaceV2();


const rulesUI = {
  page: document.querySelector('#rulesPage'), body: document.querySelector('#rulesTableBody'),
  search: document.querySelector('#rulesSearch'), scope: document.querySelector('#rulesScopeFilter'), category: document.querySelector('#rulesCategoryFilter'),
  severity: document.querySelector('#rulesSeverityFilter'), status: document.querySelector('#rulesStatusFilter'),
  editor: document.querySelector('#ruleEditor'), form: document.querySelector('#ruleEditorForm')
};
let rulesWorkspaceState = {dashboard:null, datasets:[], contracts:[], executions:[], selectedContractId:null, selectedTab:'library', categoryChart:null, failingChart:null, executionOutcomeChart:null, executionTrendChart:null, executionPage:1, executionPageSize:20, contractFindingPage:1, contractFindingPageSize:6};

async function loadRulesWorkspace() {
  const [dashRes, datasetsRes, contractsRes, executionsRes] = await Promise.all([
    fetch('/quality-rules/dashboard'), fetch('/datasets'), fetch('/quality-rules/contracts'),
    fetch('/quality-rules/executions?page=1&page_size=200')
  ]);
  if (!dashRes.ok) { setStatus('Unable to load Rules & Contracts.'); return; }
  rulesWorkspaceState.dashboard = await dashRes.json();
  rulesWorkspaceState.datasets = datasetsRes.ok ? await datasetsRes.json() : [];
  rulesWorkspaceState.contracts = contractsRes.ok ? await contractsRes.json() : [];
  const executionPayload = executionsRes.ok ? await executionsRes.json() : {items:[]};
  rulesWorkspaceState.executions = executionPayload.items || [];
  renderRulesMetrics(); renderRulesFilters(); renderRulesTable(); renderRulesCharts(); renderRuleActivity();
  renderContracts(); renderAssignments(); renderExecutionHistory(); populateContractDatasetOptions();
}
function renderRulesMetrics(){const m=rulesWorkspaceState.dashboard.metrics;setText('#rulesMetricTotal',m.total_rules);setText('#rulesMetricActive',`${m.active_rules} active \u00b7 ${m.total_rules-m.active_rules} inactive`);setText('#rulesMetricAssigned',m.assigned_datasets);setText('#rulesMetricContracts',m.contracted_datasets);setText('#rulesMetricExecutions',m.executions);setText('#rulesMetricFailing',m.failing);setText('#rulesFailureRate',`${m.failure_rate}% failure rate`)}
function renderRulesFilters(){const cats=[...new Set(rulesWorkspaceState.dashboard.rules.map(r=>r.category))].sort();const current=rulesUI.category.value;rulesUI.category.innerHTML='<option value="all">All categories</option>'+cats.map(c=>`<option value="${escapeHtml(c)}">${escapeHtml(titleCase(c))}</option>`).join('');rulesUI.category.value=cats.includes(current)?current:'all'}
function filteredRules(){const q=rulesUI.search.value.trim().toLowerCase();return rulesWorkspaceState.dashboard.rules.filter(r=>(!q||`${r.name} ${r.description||''}`.toLowerCase().includes(q))&&(rulesUI.scope.value==='all'||r.scope===rulesUI.scope.value)&&(rulesUI.category.value==='all'||r.category===rulesUI.category.value)&&(rulesUI.severity.value==='all'||r.severity===rulesUI.severity.value)&&(rulesUI.status.value==='all'||(rulesUI.status.value==='active')===r.is_active))}
function renderRulesTable(){const rows=filteredRules();setText('#rulesCountLabel',`${rows.length} rules`);rulesUI.body.innerHTML=rows.map(r=>`<tr><td><strong>${escapeHtml(r.name)}</strong><small>${escapeHtml(r.description||'No description')}</small></td><td>${escapeHtml(titleCase(r.scope))}</td><td>${escapeHtml(r.column_name||'\u2014')}</td><td><span class="chip">${escapeHtml(titleCase(r.category))}</span></td><td><span class="severity-badge severity-${r.severity}">${escapeHtml(titleCase(r.severity))}</span></td><td><span class="rule-status ${r.is_active?'':'inactive'}">${r.is_active?'Active':'Inactive'}</span></td><td>${r.assignment_count||0}</td><td>${r.last_executed_at?new Date(r.last_executed_at).toLocaleString():'Never'}</td><td><button class="icon-button" data-edit-rule="${r.id}" aria-label="Edit rule">\u22ee</button></td></tr>`).join('')||'<tr><td colspan="9" class="empty">No rules match the current filters.</td></tr>';document.querySelectorAll('[data-edit-rule]').forEach(b=>b.addEventListener('click',()=>openRuleEditor(Number(b.dataset.editRule))))}
function renderRulesCharts(){if(typeof Chart==='undefined')return;const rules=rulesWorkspaceState.dashboard.rules;const categoryCounts={};rules.forEach(r=>categoryCounts[r.category]=(categoryCounts[r.category]||0)+1);rulesWorkspaceState.categoryChart?.destroy();rulesWorkspaceState.categoryChart=new Chart(document.querySelector('#ruleCategoryChart'),{type:'doughnut',data:{labels:Object.keys(categoryCounts).map(titleCase),datasets:[{data:Object.values(categoryCounts)}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right'}}}});const byRule={};rulesWorkspaceState.dashboard.recent_executions.filter(e=>e.outcome==='failed').forEach(e=>{byRule[e.rule_name]=(byRule[e.rule_name]||0)+1});const top=Object.entries(byRule).sort((a,b)=>b[1]-a[1]).slice(0,7);rulesWorkspaceState.failingChart?.destroy();rulesWorkspaceState.failingChart=new Chart(document.querySelector('#failingRulesChart'),{type:'bar',data:{labels:top.map(x=>x[0]),datasets:[{label:'Failures',data:top.map(x=>x[1])}]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,ticks:{precision:0}}}}})}
function renderRuleActivity(){document.querySelector('#ruleRecentActivity').innerHTML=rulesWorkspaceState.dashboard.recent_executions.slice(0,8).map(e=>`<div class="rule-activity-item"><strong>${escapeHtml(e.rule_name)} \u00b7 ${escapeHtml(titleCase(e.outcome))}</strong><small>${new Date(e.executed_at).toLocaleString()} \u00b7 ${e.affected_rows} affected rows</small></div>`).join('')||'<p class="empty">No rule executions yet.</p>'}
function contractStatusBadge(status){return `<span class="contract-status contract-status-${escapeHtml(status)}">${escapeHtml(titleCase(status))}</span>`}
function validationBadge(status){const label=status==='passed'?'Passed':status==='failed'?'Failed':'Not validated';return `<span class="validation-status validation-${escapeHtml(status)}">${label}</span>`}
function renderContracts(){
  const q=(document.querySelector('#contractSearch')?.value||'').trim().toLowerCase();
  const rows=rulesWorkspaceState.contracts.filter(c=>!q||`${c.name} ${c.dataset_name||''} ${c.description||''}`.toLowerCase().includes(q));
  setText('#contractMetricTotal',rulesWorkspaceState.contracts.length);
  setText('#contractMetricPublished',rulesWorkspaceState.contracts.filter(c=>c.status==='published').length);
  setText('#contractMetricPassed',rulesWorkspaceState.contracts.filter(c=>c.validation_status==='passed').length);
  setText('#contractMetricFailed',rulesWorkspaceState.contracts.filter(c=>c.validation_status!=='passed').length);
  const target=document.querySelector('#contractsGrid');
  target.innerHTML=`<table class="contract-table"><thead><tr><th>Contract</th><th>Dataset</th><th>Version</th><th>Status</th><th>Validation</th><th>Updated</th><th></th></tr></thead><tbody>${rows.map(c=>`<tr class="${rulesWorkspaceState.selectedContractId===c.id?'selected':''}" data-contract-row="${c.id}"><td><strong>${escapeHtml(c.name)}</strong><small>${escapeHtml(c.description||'No description')}</small></td><td>${escapeHtml(c.dataset_name||'\u2014')}</td><td>v${c.version}</td><td>${contractStatusBadge(c.status)}</td><td>${validationBadge(c.validation_status)}</td><td>${new Date(c.updated_at).toLocaleString()}</td><td><button class="icon-button" data-contract-menu="${c.id}" aria-label="Open contract">\u203a</button></td></tr>`).join('')}</tbody></table>`;
  if(!rows.length)target.innerHTML='<p class="empty">No contracts match the current search.</p>';
  document.querySelectorAll('[data-contract-row]').forEach(row=>row.addEventListener('click',()=>selectContract(Number(row.dataset.contractRow))));
  const selected=rulesWorkspaceState.contracts.find(c=>c.id===rulesWorkspaceState.selectedContractId)||rulesWorkspaceState.contracts[0];
  if(selected){rulesWorkspaceState.selectedContractId=selected.id;renderContractDetail(selected);renderContractFindings(selected)}else{document.querySelector('#contractDetailPanel').innerHTML='<p class="empty">Create or generate a contract to begin governance.</p>';renderContractFindings(null)}
}
function contractFindingLabel(item){return item.rule_name||item.column||titleCase(item.kind||'violation')}
function renderContractFindings(contract){
  const target=document.querySelector('#contractValidationRegistry');
  if(!target)return;
  const violations=contract?.validation?.violations||[];
  const total=violations.length;
  const size=rulesWorkspaceState.contractFindingPageSize;
  const pages=Math.max(1,Math.ceil(total/size));
  rulesWorkspaceState.contractFindingPage=Math.min(Math.max(1,rulesWorkspaceState.contractFindingPage),pages);
  const start=(rulesWorkspaceState.contractFindingPage-1)*size;
  const rows=violations.slice(start,start+size);
  const heading=contract?`${escapeHtml(contract.name)} validation findings`:'Validation findings';
  const body=rows.length?rows.map((item,index)=>`<tr><td><strong>${escapeHtml(contractFindingLabel(item))}</strong><small>${escapeHtml(item.message||'Contract requirement failed.')}</small></td><td>${escapeHtml(item.column||'Dataset')}</td><td>${escapeHtml(item.rule_type||item.kind||'Constraint')}</td><td>${escapeHtml(String(item.expected??'Defined contract requirement'))}</td><td>${escapeHtml(String(item.observed??'Failed'))}</td><td>${Number(item.affected_rows||0)}</td><td>${escapeHtml(String(contract?.validation?.dataset_version??'--'))}</td></tr>`).join(''):`<tr><td colspan="7" class="empty">${contract&&contract.validation_status==='passed'?'No current contract violations.':'Validate the selected contract to view findings.'}</td></tr>`;
  target.innerHTML=`<div class="contract-findings-heading"><div><h3>${heading}</h3><p>${total?`${total} current violation${total===1?'':'s'} from audit ${escapeHtml(contract?.validation?.audit_id||contract?.source_audit_id||'--')}`:'Validation evidence for the selected contract.'}</p></div><span>${total} finding${total===1?'':'s'}</span></div><div class="contract-findings-table-wrap"><table class="contract-findings-table"><thead><tr><th>Finding</th><th>Column</th><th>Constraint</th><th>Expected</th><th>Observed</th><th>Affected rows</th><th>Dataset version</th></tr></thead><tbody>${body}</tbody></table></div><div class="contract-findings-pagination"><span>Showing ${total?start+1:0}-${Math.min(start+size,total)} of ${total}</span><div><button type="button" class="secondary-button" data-contract-findings-page="prev" ${rulesWorkspaceState.contractFindingPage<=1?'disabled':''}>Previous</button><span>Page ${rulesWorkspaceState.contractFindingPage} of ${pages}</span><button type="button" class="secondary-button" data-contract-findings-page="next" ${rulesWorkspaceState.contractFindingPage>=pages?'disabled':''}>Next</button></div></div>`;
  target.querySelectorAll('[data-contract-findings-page]').forEach(button=>button.addEventListener('click',()=>{rulesWorkspaceState.contractFindingPage+=button.dataset.contractFindingsPage==='next'?1:-1;renderContractFindings(contract)}));
}
function renderContractDetail(c){
  const contract=c.contract||{};const required=contract.required_columns||[];const types=contract.expected_types||{};const validation=c.validation||{};
  const lifecycleActions=c.status==='published'?`<button data-contract-status="archived" class="secondary-button">Archive</button>`:c.status==='archived'?`<button data-contract-status="draft" class="secondary-button">Return to draft</button>`:`<button data-contract-status="published">Publish contract</button>`;
  const violations=validation.violations||[];
  const validationDetails=violations.length?`<div class="contract-validation-results"><h3>Validation findings</h3>${violations.map(item=>`<article><div><strong>${escapeHtml(item.rule_name||item.column||titleCase(item.kind||'violation'))}</strong><span>${escapeHtml(item.message||'Contract requirement failed.')}</span></div><small>${item.column?`Column: ${escapeHtml(item.column)} · `:''}${Number(item.affected_rows||0)} affected row(s)</small></article>`).join('')}</div>`:'';
  document.querySelector('#contractDetailPanel').innerHTML=`<div class="card-heading"><div><p class="eyebrow">Selected contract</p><h2>${escapeHtml(c.name)}</h2></div>${contractStatusBadge(c.status)}</div><div class="contract-detail-meta"><span>Dataset<strong>${escapeHtml(c.dataset_name||'\u2014')}</strong></span><span>Version<strong>v${c.version}</strong></span><span>Validation<strong>${escapeHtml(titleCase(c.validation_status))}</strong></span><span>Source audit<strong>${escapeHtml(c.source_audit_id||'Manual')}</strong></span></div><div class="contract-requirement-summary"><article><strong>${required.length}</strong><span>Required columns</span></article><article><strong>${Object.keys(types).length}</strong><span>Type constraints</span></article><article><strong>${Object.keys(contract.allowed_values||{}).length}</strong><span>Allowed-value sets</span></article><article><strong>${validation.violation_count||0}</strong><span>Current violations</span></article></div><div class="contract-detail-actions"><button data-edit-contract="${c.id}" class="secondary-button">Edit new version</button><button data-validate-contract="${c.id}">Validate now</button><button data-view-contract-versions="${c.id}" class="secondary-button">Version history</button>${lifecycleActions}</div><div class="contract-definition-preview"><h3>Definition</h3><pre>${escapeHtml(JSON.stringify(contract,null,2))}</pre></div>`;
  document.querySelector('[data-edit-contract]')?.addEventListener('click',()=>openContractEditor(c.id));
  document.querySelector('[data-validate-contract]')?.addEventListener('click',()=>validateContract(c.id));
  document.querySelector('[data-view-contract-versions]')?.addEventListener('click',()=>showContractVersions(c.id));
  document.querySelector('[data-contract-status]')?.addEventListener('click',e=>transitionContractStatus(c.id,e.currentTarget.dataset.contractStatus));
}
function selectContract(id){rulesWorkspaceState.selectedContractId=id;rulesWorkspaceState.contractFindingPage=1;renderContracts()}
function populateContractDatasetOptions(){const options=rulesWorkspaceState.datasets.map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');const el=document.querySelector('#contractDataset');if(el)el.innerHTML=options}
async function populateContractDefinitionFromDataset({force=false}={}){
  const editorId=document.querySelector('#contractEditorId')?.value;
  if(editorId&&!force)return;
  const datasetId=Number(document.querySelector('#contractDataset')?.value||0);
  const textarea=document.querySelector('#contractDefinition');
  const status=document.querySelector('#contractDefinitionStatus');
  const dataset=rulesWorkspaceState.datasets.find(item=>Number(item.id)===datasetId);
  if(!textarea||!status)return;
  if(!dataset){textarea.value='{}';status.textContent='Select a dataset to generate the contract definition.';return;}
  if(!dataset.latest_audit_id){textarea.value='{}';status.textContent='Run a completed audit for this dataset before creating its contract.';return;}
  textarea.readOnly=true;
  textarea.setAttribute('aria-busy','true');
  status.textContent='Generating from the latest completed audit...';
  try{
    const response=await fetch(`/audits/${encodeURIComponent(dataset.latest_audit_id)}/contract`);
    const payload=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(payload.detail||'Unable to generate the contract definition.');
    textarea.value=JSON.stringify(payload,null,2);
    status.textContent=`Generated from audit ${dataset.latest_audit_id}. Review the definition, then save the contract version.`;
  }catch(error){
    textarea.value='{}';
    status.textContent=error.message||'Unable to generate the contract definition.';
  }finally{
    textarea.readOnly=false;
    textarea.removeAttribute('aria-busy');
  }
}
async function openContractEditor(id=null){
  const c=id?rulesWorkspaceState.contracts.find(x=>x.id===id):null;
  setText('#contractEditorTitle',c?'Edit Contract':'Create Contract');
  document.querySelector('#contractEditorId').value=c?.id||'';
  populateContractDatasetOptions();document.querySelector('#contractDataset').value=c?.dataset_id||rulesWorkspaceState.datasets[0]?.id||'';
  document.querySelector('#contractName').value=c?.name||'';document.querySelector('#contractDescription').value=c?.description||'';
  document.querySelector('#contractStatus').value=c?.status||'draft';document.querySelector('#contractDefinition').value=JSON.stringify(c?.contract||{},null,2);
  document.querySelector('#contractDefinitionStatus').textContent=c?'Existing definition loaded. Saving creates the next contract version.':'';
  document.querySelector('#contractEditor').classList.remove('hidden');
  if(!c)await populateContractDefinitionFromDataset({force:true});
}
function closeContractEditor(){document.querySelector('#contractEditor').classList.add('hidden')}
async function saveContract(event){event.preventDefault();let definition={};try{definition=JSON.parse(document.querySelector('#contractDefinition').value||'{}')}catch{return setStatus('Contract definition must be valid JSON.')}
  const id=document.querySelector('#contractEditorId').value;const payload={dataset_id:Number(document.querySelector('#contractDataset').value),name:document.querySelector('#contractName').value,description:document.querySelector('#contractDescription').value||null,status:document.querySelector('#contractStatus').value,contract:definition};
  const response=await fetch(id?`/quality-rules/contracts/${id}`:'/quality-rules/contracts',{method:id?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!response.ok){const p=await response.json().catch(()=>({}));return setStatus(p.detail||'Unable to save contract.')}
  const saved=await response.json();rulesWorkspaceState.selectedContractId=saved.id;closeContractEditor();setStatus(id?'Contract version created.':'Contract created.');await loadRulesWorkspace();showRulesTab('contracts');
}
function openContractGenerator(){if(!rulesWorkspaceState.datasets.length)return setStatus('Register and audit a dataset first.');const select=document.querySelector('#contractGeneratorDataset');select.innerHTML=rulesWorkspaceState.datasets.map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');document.querySelector('#contractGenerator').classList.remove('hidden');renderContractGeneratorContext()}
function closeContractGenerator(){document.querySelector('#contractGenerator').classList.add('hidden');document.querySelector('#contractGeneratorError').classList.add('hidden')}
function renderContractGeneratorContext(){const id=Number(document.querySelector('#contractGeneratorDataset').value);const d=rulesWorkspaceState.datasets.find(x=>x.id===id);const existing=rulesWorkspaceState.contracts.find(c=>c.dataset_id===id);document.querySelector('#contractGeneratorContext').innerHTML=d?`<div><span>Latest audit</span><strong>${d.latest_audit_id?escapeHtml(d.latest_audit_id):'No completed audit'}</strong></div><div><span>Current contract</span><strong>${existing?`v${existing.version} \u00b7 ${titleCase(existing.status)}`:'None'}</strong></div>`:''}
async function generateContractFromAudit(){const datasetId=Number(document.querySelector('#contractGeneratorDataset').value);const error=document.querySelector('#contractGeneratorError');error.classList.add('hidden');const response=await fetch(`/quality-rules/contracts/generate/${datasetId}`,{method:'POST'});const p=await response.json().catch(()=>({}));if(!response.ok){error.textContent=p.detail||'Unable to generate contract.';error.classList.remove('hidden');return}rulesWorkspaceState.selectedContractId=p.id;closeContractGenerator();setStatus(`Contract version ${p.version} generated from the latest audit.`);await loadRulesWorkspace();showRulesTab('contracts')}
async function transitionContractStatus(id,status){const response=await fetch(`/quality-rules/contracts/${id}/status`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});const p=await response.json().catch(()=>({}));if(!response.ok)return setStatus(p.detail||'Unable to update contract status.');rulesWorkspaceState.selectedContractId=p.id;setStatus(`Contract moved to ${titleCase(status)}.`);await loadRulesWorkspace();showRulesTab('contracts')}
async function validateContract(id){const response=await fetch(`/quality-rules/contracts/${id}/validate`,{method:'POST'});const p=await response.json().catch(()=>({}));if(!response.ok)return setStatus(p.detail||'Unable to validate contract.');setStatus(p.validation_status==='passed'?'Contract validation passed.':`Contract validation found ${p.validation?.violation_count||0} violation(s).`);await loadRulesWorkspace();showRulesTab('contracts')}
async function showContractVersions(id){const response=await fetch(`/quality-rules/contracts/${id}/versions`);if(!response.ok)return setStatus('Unable to load contract versions.');const rows=await response.json();document.querySelector('#contractDetailPanel').innerHTML=`<div class="card-heading"><div><p class="eyebrow">Version history</p><h2>${escapeHtml(rows[0]?.name||'Contract')}</h2></div><button id="backToContractDetail" class="secondary-button">Back</button></div><div class="contract-version-list">${rows.map(v=>`<article><strong>Version ${v.version}</strong>${contractStatusBadge(v.status)}<span>${new Date(v.created_at).toLocaleString()}</span><small>${escapeHtml(v.description||'No description')}</small></article>`).join('')}</div>`;document.querySelector('#backToContractDetail').addEventListener('click',()=>renderContracts())}

function renderAssignments(){
  const assignments=rulesWorkspaceState.dashboard.assignments;const rules=rulesWorkspaceState.dashboard.rules;const datasets=rulesWorkspaceState.datasets;
  const query=(document.querySelector('#assignmentSearch')?.value||'').trim().toLowerCase();
  const active=assignments.length, coveredDatasets=new Set(assignments.map(a=>a.dataset_id)).size, coveredRules=new Set(assignments.map(a=>a.rule_id)).size;
  setText('#assignmentMetricTotal',active);setText('#assignmentMetricDatasets',coveredDatasets);setText('#assignmentMetricRules',coveredRules);setText('#assignmentMetricCoverage',datasets.length?`${Math.round(coveredDatasets/datasets.length*100)}%`:'0%');
  const ruleSelect=document.querySelector('#bulkAssignmentRules'),datasetSelect=document.querySelector('#bulkAssignmentDatasets');
  if(ruleSelect)ruleSelect.innerHTML=rules.map(r=>`<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');if(datasetSelect)datasetSelect.innerHTML=datasets.map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
  const rows=datasets.filter(d=>!query||d.name.toLowerCase().includes(query)||rules.some(r=>r.name.toLowerCase().includes(query)&&assignments.some(a=>a.dataset_id===d.id&&a.rule_id===r.id)));
  document.querySelector('#assignmentsGrid').innerHTML=`<table class="assignment-table"><thead><tr><th>Dataset</th><th>Assigned rules</th><th>Coverage</th><th>Add rule</th></tr></thead><tbody>${rows.map(d=>{const ids=assignments.filter(a=>a.dataset_id===d.id).map(a=>a.rule_id);const assigned=rules.filter(r=>ids.includes(r.id));return `<tr><td><strong>${escapeHtml(d.name)}</strong><small>${escapeHtml(d.environment)}</small></td><td><div class="assignment-chips">${assigned.map(r=>`<button class="assignment-chip" data-unassign-rule="${r.id}" data-unassign-dataset="${d.id}">${escapeHtml(r.name)} \u00d7</button>`).join('')||'<span class="muted">No rules assigned</span>'}</div></td><td><strong>${assigned.length}</strong> of ${rules.length}</td><td><select data-assignment-dataset="${d.id}"><option value="">Select a rule\u2026</option>${rules.filter(r=>!ids.includes(r.id)).map(r=>`<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('')}</select></td></tr>`}).join('')}</tbody></table>`;
  document.querySelectorAll('[data-assignment-dataset]').forEach(el=>el.addEventListener('change',async()=>{if(!el.value)return;await fetch(`/quality-rules/${el.value}/assign/${el.dataset.assignmentDataset}`,{method:'POST'});setStatus('Rule assigned.');await loadRulesWorkspace();showRulesTab('assignments')}));
  document.querySelectorAll('[data-unassign-rule]').forEach(b=>b.addEventListener('click',async()=>{await fetch(`/quality-rules/${b.dataset.unassignRule}/assign/${b.dataset.unassignDataset}`,{method:'DELETE'});setStatus('Rule assignment removed.');await loadRulesWorkspace();showRulesTab('assignments')}));
}
async function applyBulkAssignment(action){const ruleIds=[...document.querySelector('#bulkAssignmentRules').selectedOptions].map(o=>Number(o.value));const datasetIds=[...document.querySelector('#bulkAssignmentDatasets').selectedOptions].map(o=>Number(o.value));if(!ruleIds.length||!datasetIds.length)return setStatus('Select at least one rule and one dataset.');const response=await fetch('/quality-rules/assignments/bulk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rule_ids:ruleIds,dataset_ids:datasetIds,action})});const p=await response.json().catch(()=>({}));if(!response.ok)return setStatus(p.detail||'Unable to update assignments.');setStatus(`${p.changed} assignment(s) updated.`);await loadRulesWorkspace();showRulesTab('assignments')}

function filteredExecutions(){const q=(document.querySelector('#executionSearch')?.value||'').trim().toLowerCase(),outcome=document.querySelector('#executionOutcomeFilter')?.value||'all',rule=document.querySelector('#executionRuleFilter')?.value||'all',dataset=document.querySelector('#executionDatasetFilter')?.value||'all';return rulesWorkspaceState.executions.filter(e=>(!q||e.rule_name.toLowerCase().includes(q))&&(outcome==='all'||e.outcome===outcome)&&(rule==='all'||String(e.rule_id)===rule)&&(dataset==='all'||e.dataset_name===dataset))}
function renderExecutionHistory(){
  const all=rulesWorkspaceState.executions,rows=filteredExecutions(),passed=all.filter(e=>e.outcome==='passed').length,failed=all.filter(e=>e.outcome==='failed').length;
  setText('#executionMetricTotal',all.length);setText('#executionMetricPassed',passed);setText('#executionMetricFailed',failed);setText('#executionMetricRate',all.length?`${(failed/all.length*100).toFixed(1)}%`:'0%');
  const ruleFilter=document.querySelector('#executionRuleFilter'),datasetFilter=document.querySelector('#executionDatasetFilter');if(ruleFilter&&ruleFilter.options.length<=1)ruleFilter.innerHTML='<option value="all">All rules</option>'+rulesWorkspaceState.dashboard.rules.map(r=>`<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');if(datasetFilter&&datasetFilter.options.length<=1)datasetFilter.innerHTML='<option value="all">All datasets</option>'+rulesWorkspaceState.datasets.map(d=>`<option value="${escapeHtml(d.name)}">${escapeHtml(d.name)}</option>`).join('');
  const pages=Math.max(1,Math.ceil(rows.length/rulesWorkspaceState.executionPageSize));if(rulesWorkspaceState.executionPage>pages)rulesWorkspaceState.executionPage=pages;const start=(rulesWorkspaceState.executionPage-1)*rulesWorkspaceState.executionPageSize;const visible=rows.slice(start,start+rulesWorkspaceState.executionPageSize);
  document.querySelector('#executionHistoryTable').innerHTML=`<div class="rules-table-wrap"><table class="execution-table"><thead><tr><th>Rule</th><th>Dataset</th><th>Outcome</th><th>Affected</th><th>Rate</th><th>Executed</th><th>Audit</th></tr></thead><tbody>${visible.map(e=>`<tr><td><strong>${escapeHtml(e.rule_name)}</strong><small>${escapeHtml(e.message||'')}</small></td><td>${escapeHtml(e.dataset_name||'\u2014')}</td><td><span class="execution-outcome outcome-${e.outcome}">${escapeHtml(titleCase(e.outcome))}</span></td><td>${e.affected_rows}</td><td>${(Number(e.affected_rate || 0) * 100).toFixed(2)}%</td><td>${new Date(e.executed_at).toLocaleString()}</td><td><button class="text-link" data-open-execution-audit="${escapeHtml(e.audit_id)}">Open audit</button></td></tr>`).join('')||'<tr><td colspan="7" class="empty">No executions match the current filters.</td></tr>'}</tbody></table></div>`;
  document.querySelector('#executionPagination').innerHTML=`<span>Showing ${rows.length?start+1:0}\u2013${Math.min(start+visible.length,rows.length)} of ${rows.length}</span><div><button class="secondary-button" id="executionPrevPage" ${rulesWorkspaceState.executionPage<=1?'disabled':''}>Previous</button><span>Page ${rulesWorkspaceState.executionPage} of ${pages}</span><button class="secondary-button" id="executionNextPage" ${rulesWorkspaceState.executionPage>=pages?'disabled':''}>Next</button></div>`;
  document.querySelector('#executionPrevPage')?.addEventListener('click',()=>{rulesWorkspaceState.executionPage--;renderExecutionHistory()});document.querySelector('#executionNextPage')?.addEventListener('click',()=>{rulesWorkspaceState.executionPage++;renderExecutionHistory()});document.querySelectorAll('[data-open-execution-audit]').forEach(b=>b.addEventListener('click',async()=>{await openAudit(b.dataset.openExecutionAudit);navigateToPage('audit')}));renderExecutionCharts(all);
}
function renderExecutionCharts(rows){if(typeof Chart==='undefined')return;const passed=rows.filter(e=>e.outcome==='passed').length,failed=rows.filter(e=>e.outcome==='failed').length;rulesWorkspaceState.executionOutcomeChart?.destroy();rulesWorkspaceState.executionOutcomeChart=new Chart(document.querySelector('#executionOutcomeChart'),{type:'doughnut',data:{labels:['Passed','Failed'],datasets:[{data:[passed,failed]}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'}}}});const buckets={};rows.filter(e=>e.outcome==='failed').forEach(e=>{const key=new Date(e.executed_at).toLocaleDateString();buckets[key]=(buckets[key]||0)+1});const labels=Object.keys(buckets).slice(-14);rulesWorkspaceState.executionTrendChart?.destroy();rulesWorkspaceState.executionTrendChart=new Chart(document.querySelector('#executionTrendChart'),{type:'line',data:{labels,datasets:[{label:'Failures',data:labels.map(k=>buckets[k]),tension:.3,fill:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}}}}})}
async function refreshRuleBuilderDatasets(preferredDatasetId=''){
  const datasetSelect=document.querySelector('#ruleBuilderDataset');
  if(!datasetSelect)return [];
  datasetSelect.disabled=true;
  datasetSelect.innerHTML='<option value="">Loading datasets\u2026</option>';
  try{
    const response=await fetch('/datasets');
    if(!response.ok)throw new Error('Unable to load registered datasets.');
    const datasets=await response.json();
    rulesWorkspaceState.datasets=Array.isArray(datasets)?datasets:[];
    datasetSelect.innerHTML='<option value="">Select a dataset</option>'+rulesWorkspaceState.datasets.map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
    const preferred=String(preferredDatasetId||'');
    if(preferred&&rulesWorkspaceState.datasets.some(d=>String(d.id)===preferred))datasetSelect.value=preferred;
    else if(rulesWorkspaceState.datasets.length===1)datasetSelect.value=String(rulesWorkspaceState.datasets[0].id);
    datasetSelect.disabled=false;
    return rulesWorkspaceState.datasets;
  }catch(error){
    datasetSelect.innerHTML='<option value="">Unable to load datasets</option>';
    datasetSelect.disabled=true;
    setStatus(error.message||'Unable to load registered datasets.');
    return [];
  }
}
async function openRuleEditor(id=null){
  const r=id?rulesWorkspaceState.dashboard.rules.find(x=>x.id===id):null;
  document.querySelector('#ruleEditorTitle').textContent=r?'Edit Rule':'Custom Rule Builder';
  document.querySelector('#ruleEditorId').value=r?.id||'';
  document.querySelector('#ruleName').value=r?.name||'';
  document.querySelector('#ruleType').value=r?.rule_type||'required';
  document.querySelector('#ruleScope').value=r?.scope||'column';
  document.querySelector('#ruleCategory').value=r?.category||'validity';
  document.querySelector('#ruleSeverity').value=r?.severity||'medium';
  document.querySelector('#ruleDescription').value=r?.description||'';
  document.querySelector('#ruleParameters').value=JSON.stringify(r?.parameters||{},null,2);
  document.querySelector('#ruleRecommendation').value=r?.recommendation||'';
  document.querySelector('#ruleActive').checked=r?.is_active??true;
  document.querySelector('#deleteRuleButton').classList.toggle('hidden',!r);
  const assignment=r?(rulesWorkspaceState.dashboard.assignments||[]).find(a=>a.rule_id===r.id):null;
  await refreshRuleBuilderDatasets(assignment?.dataset_id||'');
  document.querySelector('#ruleAssignAfterSave').checked=Boolean(assignment)||Boolean(document.querySelector('#ruleBuilderDataset').value);
  syncRuleAssignmentAvailability();
  await loadRuleBuilderColumns(r?.column_name||'');
  renderGuidedRuleParameters(r?.parameters||{});
  document.querySelector('#ruleTestResult').innerHTML='<p class="muted">Select a dataset and configure the rule, then run a test.</p>';
  rulesUI.editor.classList.remove('hidden');
}
function closeRuleEditor(){rulesUI.editor.classList.add('hidden')}
function loadSampleQualityRule(){
  document.querySelector('#ruleName').value='Customer Email Format';
  document.querySelector('#ruleType').value='email';
  document.querySelector('#ruleScope').value='column';
  document.querySelector('#ruleCategory').value='validity';
  document.querySelector('#ruleSeverity').value='high';
  document.querySelector('#ruleDescription').value='Ensures customer email addresses use a valid and consistently structured email format.';
  document.querySelector('#ruleParameters').value=JSON.stringify({allow_blank:false,trim_whitespace:true},null,2);
  document.querySelector('#ruleRecommendation').value='Correct malformed email addresses, remove surrounding whitespace, and quarantine records that cannot be validated.';
  document.querySelector('#ruleActive').checked=true;
  document.querySelector('#ruleColumn').value='email';
  renderGuidedRuleParameters({allow_blank:false,trim_whitespace:true});
}
async function loadRuleBuilderColumns(preferred=''){
  const datasetId=document.querySelector('#ruleBuilderDataset').value;
  const column=document.querySelector('#ruleColumn');
  const options=document.querySelector('#ruleColumnOptions');
  if(preferred)column.value=preferred;
  if(options)options.innerHTML='';
  if(!datasetId)return;
  const response=await fetch(`/quality-rules/builder/context/${datasetId}`);
  if(!response.ok){
    const feedback=document.querySelector('#ruleEditorFeedback');
    if(feedback){feedback.textContent='Unable to load dataset columns. You can still enter the target column manually.';feedback.className='rule-editor-feedback error'}
    return;
  }
  const data=await response.json();
  if(options)options.innerHTML=data.columns.map(c=>`<option value="${escapeHtml(c.name)}">${escapeHtml(c.inferred_type)}</option>`).join('');
  if(preferred)column.value=preferred;
}
function renderGuidedRuleParameters(existing={}){
  const type=document.querySelector('#ruleType').value;
  const target=document.querySelector('#ruleGuidedParameters');
  const fields={
    allowed_values:`<label class="wide">Allowed values <span class="field-hint">Comma separated</span><input data-rule-param="values" value="${escapeHtml((existing.values||[]).join(', '))}"></label>`,
    regex:`<label class="wide">Required pattern<input data-rule-param="pattern" value="${escapeHtml(existing.pattern||'')}"></label>`,
    numeric_range:`<label>Minimum value<input type="number" step="any" data-rule-param="min" value="${existing.min??''}"></label><label>Maximum value<input type="number" step="any" data-rule-param="max" value="${existing.max??''}"></label>`,
    length_range:`<label>Minimum length<input type="number" min="0" data-rule-param="min" value="${existing.min??''}"></label><label>Maximum length<input type="number" min="0" data-rule-param="max" value="${existing.max??''}"></label>`,
    missing_threshold:`<label class="wide">Maximum missing percentage<input type="number" min="0" max="100" step="0.1" data-rule-param="max_rate_percent" value="${existing.max_rate!=null?Number(existing.max_rate)*100:''}"></label>`,
    expected_type:`<label class="wide">Expected type<select data-rule-param="type"><option value="text">Text</option><option value="numeric">Numeric</option><option value="datetime">Date/time</option><option value="boolean">Boolean</option></select></label>`,
    stale_days:`<label class="wide">Maximum age in days<input type="number" min="1" data-rule-param="days" value="${existing.days??30}"></label>`
  };
  target.innerHTML=fields[type]||'<p class="guided-parameter-note">This rule type does not require additional parameters.</p>';
  const typeSelect=target.querySelector('[data-rule-param="type"]');if(typeSelect)typeSelect.value=existing.type||'text';
  target.querySelectorAll('[data-rule-param]').forEach(el=>el.addEventListener('input',syncGuidedRuleParameters));
}
function syncGuidedRuleParameters(){
  const values={};document.querySelectorAll('#ruleGuidedParameters [data-rule-param]').forEach(el=>{if(el.value==='')return;const key=el.dataset.ruleParam;if(key==='values')values.values=el.value.split(',').map(v=>v.trim()).filter(Boolean);else if(key==='max_rate_percent')values.max_rate=Number(el.value)/100;else if(['min','max','days'].includes(key))values[key]=Number(el.value);else values[key]=el.value});
  document.querySelector('#ruleParameters').value=JSON.stringify(values,null,2);
}
function currentRulePayload(){
  let parameters={};
  try{parameters=JSON.parse(document.querySelector('#ruleParameters').value||'{}')}catch{throw new Error('Parameters must be valid JSON.')}
  const name=document.querySelector('#ruleName').value.trim();
  const scope=document.querySelector('#ruleScope').value;
  const columnName=document.querySelector('#ruleColumn').value.trim();
  const ruleType=document.querySelector('#ruleType').value;
  if(!name)throw new Error('Enter a rule name before saving.');
  if(scope==='column'&&!columnName)throw new Error('Enter or select a target column for this column-level rule.');
  if(scope==='dataset'&&ruleType!=='duplicate_rows')throw new Error('Dataset-level rules currently support Duplicate rows only.');
  return {name,description:document.querySelector('#ruleDescription').value.trim()||null,rule_type:ruleType,scope,column_name:scope==='column'?columnName:null,category:document.querySelector('#ruleCategory').value,severity:document.querySelector('#ruleSeverity').value,parameters,recommendation:document.querySelector('#ruleRecommendation').value.trim()||null,is_active:document.querySelector('#ruleActive').checked}
}
async function testCustomRule(){
  const datasetId=Number(document.querySelector('#ruleBuilderDataset').value);const target=document.querySelector('#ruleTestResult');if(!datasetId){target.innerHTML='<p class="error-text">Select a dataset before testing the rule.</p>';return}
  let rule;try{rule=currentRulePayload()}catch(error){target.innerHTML=`<p class="error-text">${escapeHtml(error.message)}</p>`;return}
  target.innerHTML='<p class="muted">Testing rule against the latest dataset version\u2026</p>';
  const response=await fetch('/quality-rules/builder/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:datasetId,rule})});const data=await response.json().catch(()=>({}));if(!response.ok){target.innerHTML=`<p class="error-text">${escapeHtml(data.detail||'Unable to test rule.')}</p>`;return}
  target.innerHTML=`<div class="rule-test-summary ${data.outcome}"><div><span>Outcome</span><strong>${escapeHtml(titleCase(data.outcome))}</strong></div><div><span>Affected rows</span><strong>${data.affected_rows} / ${data.total_rows}</strong></div><div><span>Affected rate</span><strong>${data.affected_percentage}%</strong></div><div><span>Estimated score impact</span><strong>-${data.estimated_score_impact}</strong></div></div><p>${escapeHtml(data.message)}</p>${data.examples?.length?`<details><summary>View safe failing examples</summary><pre>${escapeHtml(JSON.stringify(data.examples,null,2))}</pre></details>`:''}`;
}


async function saveRule(event){
  event.preventDefault();
  const saveButton=document.querySelector('#saveRuleButton');
  const feedback=document.querySelector('#ruleEditorFeedback');
  let payload;
  try{payload=currentRulePayload()}catch(error){
    if(feedback){feedback.textContent=error.message;feedback.className='rule-editor-feedback error'}
    setStatus(error.message);return;
  }
  const id=document.querySelector('#ruleEditorId').value;
  const datasetId=document.querySelector('#ruleBuilderDataset').value;
  const assignAfterSave=Boolean(datasetId)&&document.querySelector('#ruleAssignAfterSave').checked;
  if(saveButton){saveButton.disabled=true;saveButton.textContent=id?'Saving changes\u2026':'Saving rule\u2026'}
  if(feedback){feedback.textContent='Saving rule\u2026';feedback.className='rule-editor-feedback pending'}
  try{
    const response=await fetch(id?`/quality-rules/${id}`:'/quality-rules',{
      method:id?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
    });
    const saved=await parseResponse(response);
    if(!response.ok)throw new Error(saved.detail||'Unable to save rule.');
    if(assignAfterSave){
      const assignment=await fetch(`/quality-rules/${saved.id}/assign/${datasetId}`,{method:'POST'});
      const assignmentPayload=await parseResponse(assignment);
      if(!assignment.ok)throw new Error(assignmentPayload.detail||'Rule was saved, but dataset assignment failed.');
    }
    const verifyResponse=await fetch(`/quality-rules/${saved.id}`);
    const verified=await parseResponse(verifyResponse);
    if(!verifyResponse.ok||!verified?.id)throw new Error('The rule could not be verified after saving.');
    if(!rulesWorkspaceState.dashboard)rulesWorkspaceState.dashboard={rules:[],metrics:{total_rules:0,active_rules:0,assigned_datasets:0,contracted_datasets:0,executions:0,failing:0,failure_rate:0},recent_executions:[],assignments:[]};
    const currentRules=rulesWorkspaceState.dashboard.rules||[];
    const index=currentRules.findIndex(rule=>Number(rule.id)===Number(verified.id));
    const uiRule={...verified,assignment_count:assignAfterSave?1:(currentRules[index]?.assignment_count||0),last_executed_at:currentRules[index]?.last_executed_at||null};
    if(index>=0)currentRules.splice(index,1,uiRule);else currentRules.unshift(uiRule);
    rulesWorkspaceState.dashboard.rules=currentRules;
    renderRulesTable();
    closeRuleEditor();
    setStatus(id?(assignAfterSave?'Rule updated, saved, and assigned.':'Rule updated and saved.'):(assignAfterSave?'Rule created, saved, and assigned.':'Rule created and saved.'));
    await loadRulesWorkspace();
    showRulesTab('library');
  }catch(error){
    const message=error?.message||'Unable to save rule.';
    if(feedback){feedback.textContent=message;feedback.className='rule-editor-feedback error'}
    setStatus(message);
  }finally{
    if(saveButton){saveButton.disabled=false;saveButton.textContent='Save rule'}
  }
}
async function deleteCurrentRule(){const id=document.querySelector('#ruleEditorId').value;if(!id||!(await confirmAppAction({title:'Delete rule?',description:'This removes the rule and its active assignments. Existing execution evidence remains available.',confirmLabel:'Delete rule',danger:true})))return;const response=await fetch(`/quality-rules/${id}`,{method:'DELETE'});if(response.ok){closeRuleEditor();setStatus('Rule deleted.');await loadRulesWorkspace()}}
function showRulesTab(name){rulesWorkspaceState.selectedTab=name;document.querySelectorAll('[data-rules-tab]').forEach(b=>b.classList.toggle('active',b.dataset.rulesTab===name));['library','contracts','assignments','history'].forEach(n=>document.querySelector(`#rules${titleCase(n)}Tab`)?.classList.toggle('hidden',n!==name))}
function titleCase(value){return String(value||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}

document.querySelector('#newContractButton')?.addEventListener('click',()=>openContractEditor());document.querySelector('#generateContractButton')?.addEventListener('click',openContractGenerator);document.querySelector('#closeContractGenerator')?.addEventListener('click',closeContractGenerator);document.querySelector('#cancelContractGenerator')?.addEventListener('click',closeContractGenerator);document.querySelector('#confirmContractGeneration')?.addEventListener('click',generateContractFromAudit);document.querySelector('#contractGeneratorDataset')?.addEventListener('change',renderContractGeneratorContext);document.querySelector('#closeContractEditor')?.addEventListener('click',closeContractEditor);document.querySelector('#cancelContractEditor')?.addEventListener('click',closeContractEditor);document.querySelector('#contractDataset')?.addEventListener('change',()=>populateContractDefinitionFromDataset({force:true}));document.querySelector('#contractEditorForm')?.addEventListener('submit',saveContract);document.querySelector('#contractSearch')?.addEventListener('input',renderContracts);document.querySelector('#bulkAssignButton')?.addEventListener('click',()=>applyBulkAssignment('assign'));document.querySelector('#bulkUnassignButton')?.addEventListener('click',()=>applyBulkAssignment('unassign'));document.querySelector('#refreshAssignmentsButton')?.addEventListener('click',loadRulesWorkspace);document.querySelector('#assignmentSearch')?.addEventListener('input',renderAssignments);document.querySelector('#exportExecutionHistoryButton')?.addEventListener('click',()=>window.open('/quality-rules/executions/export.csv','_blank'));['executionSearch','executionOutcomeFilter','executionRuleFilter','executionDatasetFilter'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener(id==='executionSearch'?'input':'change',()=>{rulesWorkspaceState.executionPage=1;renderExecutionHistory()}));document.querySelector('#executionResetFilters')?.addEventListener('click',()=>{document.querySelector('#executionSearch').value='';document.querySelector('#executionOutcomeFilter').value='all';document.querySelector('#executionRuleFilter').value='all';document.querySelector('#executionDatasetFilter').value='all';rulesWorkspaceState.executionPage=1;renderExecutionHistory()});
document.querySelector('#ruleBuilderDataset')?.addEventListener('change',()=>{syncRuleAssignmentAvailability(true);loadRuleBuilderColumns()});document.querySelector('#ruleType')?.addEventListener('change',()=>renderGuidedRuleParameters({}));document.querySelector('#ruleScope')?.addEventListener('change',()=>{const datasetScope=document.querySelector('#ruleScope').value==='dataset';document.querySelector('#ruleColumn').disabled=datasetScope;if(datasetScope){document.querySelector('#ruleType').value='duplicate_rows';renderGuidedRuleParameters({})}});document.querySelector('#testRuleButton')?.addEventListener('click',testCustomRule);
function syncRuleAssignmentAvailability(autoCheck=false){
  const datasetSelected=Boolean(document.querySelector('#ruleBuilderDataset')?.value);
  const toggle=document.querySelector('#ruleAssignAfterSave');
  if(toggle){
    toggle.disabled=!datasetSelected;
    if(!datasetSelected)toggle.checked=false;
    else if(autoCheck)toggle.checked=true;
  }
}
document.querySelector('#newRuleButton')?.addEventListener('click',()=>openRuleEditor());document.querySelector('#loadSampleRuleButton')?.addEventListener('click',loadSampleQualityRule);document.querySelector('#closeRuleEditor')?.addEventListener('click',closeRuleEditor);document.querySelector('#cancelRuleEditor')?.addEventListener('click',closeRuleEditor);document.querySelector('#deleteRuleButton')?.addEventListener('click',deleteCurrentRule);rulesUI.form?.addEventListener('submit',saveRule);document.querySelector('#rulesRefreshButton')?.addEventListener('click',loadRulesWorkspace);document.querySelector('#rulesResetFilters')?.addEventListener('click',()=>{rulesUI.search.value='';rulesUI.scope.value=rulesUI.category.value=rulesUI.severity.value=rulesUI.status.value='all';renderRulesTable()});[rulesUI.search,rulesUI.scope,rulesUI.category,rulesUI.severity,rulesUI.status].forEach(el=>el?.addEventListener(el.tagName==='INPUT'?'input':'change',renderRulesTable));document.querySelectorAll('[data-rules-tab]').forEach(b=>b.addEventListener('click',()=>showRulesTab(b.dataset.rulesTab)));


// Feature 18: dataset versioning and version-aware audit comparison.
const versionWorkspaceState = { datasets: [], selectedDataset: null, versions: [], comparison: null, selectedAuditId: null, pendingDatasetId: null, versionPage: 1, versionsPerPage: 6, issueMovementPage: 1, issueMovementsPerPage: 5, issueMovements: [] };

async function openVersionsPage() {
  authEls.profileMenu?.classList.add('hidden');
  hideAllPages();
  const page = document.querySelector('#versionsPage');
  page?.classList.remove('hidden');
  document.querySelector('#versionsNavButton')?.classList.add('active');
  animatePage(page);
  await loadVersionDatasets();
}

async function loadVersionDatasets() {
  const response = await fetch('/datasets');
  if (!response.ok) return setStatus('Unable to load datasets for version history.');
  versionWorkspaceState.datasets = await response.json();
  const select = document.querySelector('#versionDatasetSelect');
  const current = versionWorkspaceState.pendingDatasetId ? String(versionWorkspaceState.pendingDatasetId) : select?.value;
  if (select) select.innerHTML = '<option value="">Select a dataset</option>' + versionWorkspaceState.datasets.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join('');
  if (current && versionWorkspaceState.datasets.some(item => String(item.id) === String(current))) select.value = String(current);
  versionWorkspaceState.pendingDatasetId = null;
  if (select?.value) await loadDatasetVersions(Number(select.value));
}

async function loadDatasetVersions(datasetId) {
  const response = await fetch(`/datasets/${datasetId}/versions`);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return setStatus(body.detail || 'Unable to load dataset versions.');
  versionWorkspaceState.selectedDataset = body;
  versionWorkspaceState.versions = body.versions || [];
  versionWorkspaceState.comparison = null;
  versionWorkspaceState.versionPage = 1;
  versionWorkspaceState.issueMovementPage = 1;
  versionWorkspaceState.issueMovements = [];
  document.querySelector('#versionEmptyState')?.classList.toggle('hidden', versionWorkspaceState.versions.length > 0);
  document.querySelector('#versionWorkspace')?.classList.toggle('hidden', versionWorkspaceState.versions.length === 0);
  setText('#versionCountMetric', body.version_count || 0);
  const latest = versionWorkspaceState.versions.at(-1);
  setText('#versionLatestScore', latest ? latest.score : '\u2014');
  setText('#versionLatestRisk', latest ? `${titleCase(latest.risk_level)} risk \u00b7 ${latest.row_count.toLocaleString()} rows` : 'No completed audit');
  populateVersionSelectors();
  renderVersionTimeline();
  resetVersionComparison();
}

function populateVersionSelectors() {
  const options = versionWorkspaceState.versions.map(item => `<option value="${item.audit_id}">v${item.version} \u00b7 ${new Date(item.created_at).toLocaleString()} \u00b7 score ${item.score}</option>`).join('');
  const baseline = document.querySelector('#baselineVersionSelect');
  const candidate = document.querySelector('#candidateVersionSelect');
  [baseline, candidate].forEach(el => { if (el) { el.innerHTML = options; el.disabled = versionWorkspaceState.versions.length < 1; } });
  if (versionWorkspaceState.versions.length > 1) {
    baseline.value = versionWorkspaceState.versions.at(-2).audit_id;
    candidate.value = versionWorkspaceState.versions.at(-1).audit_id;
  }
  document.querySelector('#compareVersionsButton').disabled = versionWorkspaceState.versions.length < 2;
  versionWorkspaceState.selectedAuditId = candidate?.value || null;
  document.querySelector('#openVersionAuditButton').disabled = !versionWorkspaceState.selectedAuditId;
}

function versionDeltaTone(delta) { return delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral'; }
function renderVersionTimeline() {
  const target = document.querySelector('#versionTimeline');
  if (!target) return;
  const ordered = versionWorkspaceState.versions.slice().reverse();
  const pageCount = Math.max(1, Math.ceil(ordered.length / versionWorkspaceState.versionsPerPage));
  versionWorkspaceState.versionPage = Math.min(Math.max(1, versionWorkspaceState.versionPage), pageCount);
  const start = (versionWorkspaceState.versionPage - 1) * versionWorkspaceState.versionsPerPage;
  const pageItems = ordered.slice(start, start + versionWorkspaceState.versionsPerPage);
  target.innerHTML = pageItems.map(item => {
    const originalIndex = versionWorkspaceState.versions.findIndex(version => version.audit_id === item.audit_id);
    const previous = originalIndex > 0 ? versionWorkspaceState.versions[originalIndex - 1] : null;
    const delta = previous ? Number(item.score) - Number(previous.score) : 0;
    const deltaLabel = previous ? `${signedVersionValue(delta, ' pts')}` : 'Baseline';
    return `<button class="version-timeline-row ${item.is_latest ? 'latest' : ''}" data-version-audit="${item.audit_id}"><span class="version-number">v${item.version}</span><span class="version-main"><strong>${new Date(item.created_at).toLocaleString()}</strong><small>${escapeHtml(item.source_filename || item.dataset_name)} \u00b7 ${item.row_count.toLocaleString()} rows \u00b7 ${item.column_count} columns</small></span><span class="version-score">${item.score}<small>${titleCase(item.risk_level)}</small></span><span class="version-score-delta ${versionDeltaTone(delta)}" aria-label="Score change ${deltaLabel}">${delta > 0 ? '\u25b2' : delta < 0 ? '\u25bc' : '\u2022'} ${deltaLabel}</span><span class="status-badge version-snapshot-badge">${item.is_latest ? 'Latest' : 'Snapshot'}</span></button>`;
  }).join('') || '<div class="empty-row">No versions are available.</div>';
  setText('#versionPageSummary', ordered.length ? `Showing ${start + 1}\u2013${Math.min(start + pageItems.length, ordered.length)} of ${ordered.length}` : '0 versions');
  setText('#versionPageIndicator', `${versionWorkspaceState.versionPage} of ${pageCount}`);
  const prev = document.querySelector('#versionPrevPage'), next = document.querySelector('#versionNextPage');
  if (prev) prev.disabled = versionWorkspaceState.versionPage <= 1;
  if (next) next.disabled = versionWorkspaceState.versionPage >= pageCount;
  target.querySelectorAll('[data-version-audit]').forEach(button => button.addEventListener('click', () => {
    versionWorkspaceState.selectedAuditId = button.dataset.versionAudit;
    document.querySelector('#candidateVersionSelect').value = versionWorkspaceState.selectedAuditId;
    document.querySelector('#openVersionAuditButton').disabled = false;
    target.querySelectorAll('.selected').forEach(row => row.classList.remove('selected'));
    button.classList.add('selected');
  }));
}

function resetVersionComparison() {
  setText('#versionScoreDelta', '\u2014'); setText('#versionRowDelta', '\u2014'); setText('#versionIssueDelta', '\u2014');
  setText('#versionComparisonStatus', 'Not compared');
  document.querySelector('#versionComparisonSummary').innerHTML = '<div class="version-comparison-empty">Choose a baseline and candidate version, then run the comparison.</div>';
  document.querySelector('#versionSchemaChanges').innerHTML = '<p class="muted">No comparison results yet.</p>';
  versionWorkspaceState.issueMovements = []; versionWorkspaceState.issueMovementPage = 1;
  document.querySelector('#versionIssueChanges').innerHTML = '<p class="muted">No comparison results yet.</p>';
  updateIssueMovementPagination();
}

function signedVersionValue(value, suffix = '') { const number = Number(value || 0); return `${number > 0 ? '+' : number < 0 ? '\u2212' : ''}${Math.abs(number).toLocaleString()}${suffix}`; }

async function compareDatasetVersions(event) {
  event?.preventDefault?.();
  const datasetSelect = document.querySelector('#versionDatasetSelect');
  const baselineSelect = document.querySelector('#baselineVersionSelect');
  const candidateSelect = document.querySelector('#candidateVersionSelect');
  const button = document.querySelector('#compareVersionsButton');
  const summary = document.querySelector('#versionComparisonSummary');
  const datasetId = datasetSelect?.value || '';
  const baseline = baselineSelect?.value || '';
  const candidate = candidateSelect?.value || '';
  if (!datasetId || !baseline || !candidate) {
    if (summary) summary.innerHTML = '<div class="version-comparison-empty error">Select a dataset, baseline version, and candidate version.</div>';
    return setStatus('Select both dataset versions before comparing.');
  }
  if (baseline === candidate) {
    if (summary) summary.innerHTML = '<div class="version-comparison-empty error">Baseline and candidate must be different versions.</div>';
    return setStatus('Choose two different dataset versions.');
  }
  button.disabled = true;
  button.textContent = 'Comparing\u2026';
  if (summary) summary.innerHTML = '<div class="version-comparison-empty loading">Comparing the selected versions\u2026</div>';
  try {
    const response = await fetch(`/datasets/${datasetId}/versions/compare?baseline_audit_id=${encodeURIComponent(baseline)}&candidate_audit_id=${encodeURIComponent(candidate)}`, { headers: { Accept: 'application/json' } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || 'Unable to compare dataset versions.');
    versionWorkspaceState.comparison = body;
    versionWorkspaceState.selectedAuditId = candidate;
    renderVersionComparison(body);
    setStatus('Dataset versions compared successfully.');
  } catch (error) {
    if (summary) summary.innerHTML = `<div class="version-comparison-empty error">${escapeHtml(error.message || 'Unable to compare dataset versions.')}</div>`;
    setStatus(error.message || 'Unable to compare dataset versions.');
  } finally {
    button.disabled = false;
    button.textContent = 'Compare versions';
  }
}

function renderVersionComparison(data) {
  const resolvedIssues = Array.isArray(data.resolved_issues) ? data.resolved_issues : [];
  const newIssues = Array.isArray(data.new_issues) ? data.new_issues : [];
  const persistentIssues = Array.isArray(data.persistent_issues) ? data.persistent_issues : [];
  setText('#versionScoreDelta', signedVersionValue(data.score_delta, ' pts'));
  setText('#versionRowDelta', signedVersionValue(data.row_count_delta));
  setText('#versionIssueDelta', signedVersionValue(data.issue_count_delta));
  const direction = data.score_delta > 0 ? 'Improved' : data.score_delta < 0 ? 'Regressed' : 'Stable';
  setText('#versionComparisonStatus', direction);
  document.querySelector('#versionComparisonSummary').innerHTML = `<div class="version-summary-grid"><article class="delta-card ${versionDeltaTone(data.score_delta)}"><span>Score</span><strong>${signedVersionValue(data.score_delta, ' pts')}</strong><small>${data.score_delta > 0 ? 'Improved' : data.score_delta < 0 ? 'Regressed' : 'Stable'}</small></article><article class="delta-card ${versionDeltaTone(data.row_count_delta)}"><span>Rows</span><strong>${signedVersionValue(data.row_count_delta)}</strong></article><article class="delta-card ${versionDeltaTone(data.column_count_delta)}"><span>Columns</span><strong>${signedVersionValue(data.column_count_delta)}</strong></article><article class="delta-card ${versionDeltaTone(-data.issue_count_delta)}"><span>Issues</span><strong>${signedVersionValue(data.issue_count_delta)}</strong><small>${data.issue_count_delta < 0 ? 'Fewer issues' : data.issue_count_delta > 0 ? 'More issues' : 'No change'}</small></article></div><p>${resolvedIssues.length} resolved, ${newIssues.length} new, and ${persistentIssues.length} persistent issues.</p>`;
  const added = data.schema_changes?.added_columns || [], removed = data.schema_changes?.removed_columns || [], types = data.type_changes || [];
  document.querySelector('#versionSchemaChanges').innerHTML = `<div class="change-group"><span>Added columns</span>${renderVersionChips(added, 'positive')}</div><div class="change-group"><span>Removed columns</span>${renderVersionChips(removed, 'negative')}</div><div class="change-group"><span>Type changes</span>${types.length ? types.map(item => `<div class="type-change"><strong>${escapeHtml(item.column)}</strong><small>${escapeHtml(item.before)} \u2192 ${escapeHtml(item.after)}</small></div>`).join('') : '<small class="muted">None</small>'}</div>`;
  versionWorkspaceState.issueMovements = [
    ...newIssues.map(item => ({...item, movementLabel: 'New issue', tone: 'negative'})),
    ...resolvedIssues.map(item => ({...item, movementLabel: 'Resolved', tone: 'positive'})),
    ...persistentIssues.map(item => ({...item, movementLabel: 'Persistent', tone: 'neutral'}))
  ];
  versionWorkspaceState.issueMovementPage = 1;
  renderIssueMovementPage();
  document.querySelector('#openVersionAuditButton').disabled = false;
}

function renderVersionChips(items, tone) { return items.length ? `<div class="version-chips">${items.map(item => `<span class="${tone}">${escapeHtml(item)}</span>`).join('')}</div>` : '<small class="muted">None</small>'; }
function renderIssueMovementPage() {
  const target = document.querySelector('#versionIssueChanges');
  if (!target) return;
  const items = versionWorkspaceState.issueMovements || [];
  const pageCount = Math.max(1, Math.ceil(items.length / versionWorkspaceState.issueMovementsPerPage));
  versionWorkspaceState.issueMovementPage = Math.min(Math.max(1, versionWorkspaceState.issueMovementPage), pageCount);
  const start = (versionWorkspaceState.issueMovementPage - 1) * versionWorkspaceState.issueMovementsPerPage;
  const pageItems = items.slice(start, start + versionWorkspaceState.issueMovementsPerPage);
  target.innerHTML = pageItems.length ? pageItems.map(item => `<div class="issue-movement ${item.tone}"><div><span class="movement-label">${escapeHtml(item.movementLabel)}</span><strong>${escapeHtml(item.title)}</strong></div><small>${titleCase(item.severity)} \u00b7 ${titleCase(item.category)}${item.columns?.length ? ` \u00b7 ${item.columns.map(escapeHtml).join(', ')}` : ''}</small></div>`).join('') : '<small class="muted">No issue movement.</small>';
  updateIssueMovementPagination();
}
function updateIssueMovementPagination() {
  const items = versionWorkspaceState.issueMovements || [];
  const pageCount = Math.max(1, Math.ceil(items.length / versionWorkspaceState.issueMovementsPerPage));
  const start = (versionWorkspaceState.issueMovementPage - 1) * versionWorkspaceState.issueMovementsPerPage;
  setText('#issueMovementSummary', items.length ? `Showing ${start + 1}\u2013${Math.min(start + versionWorkspaceState.issueMovementsPerPage, items.length)} of ${items.length}` : '0 movements');
  setText('#issueMovementPageIndicator', `${versionWorkspaceState.issueMovementPage} of ${pageCount}`);
  const prev = document.querySelector('#issueMovementPrev'), next = document.querySelector('#issueMovementNext');
  if (prev) prev.disabled = versionWorkspaceState.issueMovementPage <= 1;
  if (next) next.disabled = versionWorkspaceState.issueMovementPage >= pageCount;
}

function openSelectedVersionAudit() {
  if (!versionWorkspaceState.selectedAuditId) return;
  const auditId = versionWorkspaceState.selectedAuditId;
  navigateToPage('audit');
  const url = new URL(window.location.href); url.searchParams.set('audit', auditId); history.replaceState({page:'audit'}, '', url);
  loadAuditByIdV2(auditId);
}

document.querySelector('#versionDatasetSelect')?.addEventListener('change', event => event.target.value ? loadDatasetVersions(Number(event.target.value)) : resetVersionComparison());
document.querySelector('#baselineVersionSelect')?.addEventListener('change', resetVersionComparison);
document.querySelector('#candidateVersionSelect')?.addEventListener('change', event => { resetVersionComparison(); versionWorkspaceState.selectedAuditId = event.target.value; document.querySelector('#openVersionAuditButton').disabled = !event.target.value; });
if (document.querySelector('#compareVersionsButton')) document.querySelector('#compareVersionsButton').onclick = compareDatasetVersions;
document.querySelector('#refreshVersionsButton')?.addEventListener('click', loadVersionDatasets);
document.querySelector('#openVersionAuditButton')?.addEventListener('click', openSelectedVersionAudit);
document.querySelector('#versionPrevPage')?.addEventListener('click', () => { versionWorkspaceState.versionPage -= 1; renderVersionTimeline(); });
document.querySelector('#versionNextPage')?.addEventListener('click', () => { versionWorkspaceState.versionPage += 1; renderVersionTimeline(); });
document.querySelector('#issueMovementPrev')?.addEventListener('click', () => { versionWorkspaceState.issueMovementPage -= 1; renderIssueMovementPage(); });
document.querySelector('#issueMovementNext')?.addEventListener('click', () => { versionWorkspaceState.issueMovementPage += 1; renderIssueMovementPage(); });


// Legacy page-list regression marker: ["#overviewPage", "#auditPage", "#datasetsPage", "#rulesPage", "#teamPage", "#remediationPage"]

// Feature 19: schema drift monitoring.
const driftState = { payload:null, events:[], filtered:[], selected:null, pendingDatasetId:null, page:1, perPage:6, trendChart:null, severityChart:null, typeChart:null, datasets:[] };

async function openDriftPage(){
  authEls.profileMenu?.classList.add('hidden'); hideAllPages();
  const page=document.querySelector('#driftPage'); page?.classList.remove('hidden');
  document.querySelector('#driftNavButton')?.classList.add('active'); animatePage(page);
  await loadDriftDatasets(); await loadSchemaDrift();
}
async function loadDriftDatasets(){
  const response=await fetch('/datasets'); if(!response.ok)return;
  driftState.datasets=await response.json(); const select=document.querySelector('#driftDatasetFilter');
  const current=driftState.pendingDatasetId?String(driftState.pendingDatasetId):(select?.value||'all'); if(select){select.innerHTML='<option value="all">All datasets</option>'+driftState.datasets.map(x=>`<option value="${x.id}">${escapeHtml(x.name)}</option>`).join('');select.value=driftState.datasets.some(x=>String(x.id)===String(current))?String(current):'all'} driftState.pendingDatasetId=null;
}
async function loadSchemaDrift(){
  setStatus('Loading schema drift intelligence\u2026');
  const params=new URLSearchParams();
  const dataset=document.querySelector('#driftDatasetFilter')?.value||'all'; if(dataset!=='all')params.set('dataset_id',dataset);
  const type=document.querySelector('#driftTypeFilter')?.value||'all'; if(type!=='all')params.set('drift_type',type);
  const severity=document.querySelector('#driftSeverityFilter')?.value||'all'; if(severity!=='all')params.set('severity',severity);
  const status=document.querySelector('#driftStatusFilter')?.value||'all'; if(status!=='all')params.set('status',status);
  const search=document.querySelector('#driftSearch')?.value?.trim(); if(search)params.set('search',search);
  const response=await fetch(`/schema-drift?${params.toString()}`,{headers:{Accept:'application/json'}}); const body=await response.json().catch(()=>({}));
  if(!response.ok){setStatus(body.detail||'Unable to load schema drift.');return}
  driftState.payload=body; driftState.events=body.events||[]; driftState.filtered=driftState.events; driftState.page=1;
  renderDriftSummary(); renderDriftCharts(); renderDriftRows();
  if(driftState.selected){const same=driftState.events.find(x=>x.id===driftState.selected.id); same?selectDriftEvent(same):clearDriftDetail()}
  setStatus('Schema drift monitoring refreshed.');
}
function pct(part,total){return total?`${Math.round(part/total*100)}% of events`:'0% of events'}
function renderDriftSummary(){const s=driftState.payload?.summary||{};setText('#driftTotal',s.total||0);setText('#driftHigh',s.high||0);setText('#driftMedium',s.medium||0);setText('#driftLow',s.low||0);setText('#driftAverage',s.average_impact||0);setText('#driftHighRate',pct(s.high,s.total));setText('#driftMediumRate',pct(s.medium,s.total));setText('#driftLowRate',pct(s.low,s.total));setText('#driftEventCount',`(${driftState.events.length})`)}
function driftLabel(value){return titleCase(value).replace('Nullability Changed','Nullability Changed').replace('Cardinality Shift','Cardinality Shift')}
function renderDriftCharts(){if(typeof Chart==='undefined')return;const payload=driftState.payload||{};const trend=payload.trend||[];driftState.trendChart?.destroy();driftState.trendChart=new Chart(document.querySelector('#driftTrendChart'),{type:'line',data:{labels:trend.map(x=>new Date(x.date).toLocaleDateString()),datasets:[{data:trend.map(x=>x.count),label:'Events',borderColor:'#7357d8',backgroundColor:'rgba(115,87,216,.12)',fill:true,tension:.35,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{grid:{display:false}}}}});const s=payload.summary||{};driftState.severityChart?.destroy();driftState.severityChart=new Chart(document.querySelector('#driftSeverityChart'),{type:'doughnut',data:{labels:['High','Medium','Low'],datasets:[{data:[s.high||0,s.medium||0,s.low||0],backgroundColor:['#ef4444','#f59e0b','#22a06b'],borderWidth:3,borderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,cutout:'66%',plugins:{legend:{position:'right',labels:{usePointStyle:true,boxWidth:8,font:{size:10}}}}}});const entries=Object.entries(payload.type_counts||{}).sort((a,b)=>b[1]-a[1]);driftState.typeChart?.destroy();driftState.typeChart=new Chart(document.querySelector('#driftTypeChart'),{type:'bar',data:{labels:entries.map(x=>driftLabel(x[0])),datasets:[{data:entries.map(x=>x[1]),backgroundColor:['#7357d8','#557bd8','#ef6b6b','#f4a340','#5bb98c'],borderRadius:5}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,ticks:{precision:0}},y:{grid:{display:false},ticks:{font:{size:10}}}}}})}
function renderDriftRows(){const items=driftState.filtered;const pages=Math.max(1,Math.ceil(items.length/driftState.perPage));driftState.page=Math.max(1,Math.min(driftState.page,pages));const start=(driftState.page-1)*driftState.perPage;const shown=items.slice(start,start+driftState.perPage);const target=document.querySelector('#driftEventRows');target.innerHTML=shown.length?shown.map(item=>`<button type="button" class="drift-event-row ${driftState.selected?.id===item.id?'selected':''}" data-drift-id="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.dataset_name)}</strong></span><span><i class="drift-type-chip">${escapeHtml(driftLabel(item.drift_type))}</i></span><span><i class="drift-severity-chip ${item.severity}">${escapeHtml(titleCase(item.severity))}</i></span><span><i class="impact-chip ${item.severity}">${item.impact_score}</i></span><span><strong>${escapeHtml(item.description)}</strong></span><span>v${item.baseline_version} \u2192 v${item.candidate_version}</span><span><i class="drift-status-chip ${item.status}">${escapeHtml(titleCase(item.status))}</i></span><span>${new Date(item.detected_at).toLocaleString()}</span></button>`).join(''):'<div class="empty-row">No drift events match the current filters.</div>';target.querySelectorAll('[data-drift-id]').forEach(btn=>btn.addEventListener('click',()=>selectDriftEvent(items.find(x=>x.id===btn.dataset.driftId))));setText('#driftPageSummary',items.length?`Showing ${start+1}\u2013${Math.min(start+driftState.perPage,items.length)} of ${items.length}`:'0 events');setText('#driftPageIndicator',`${driftState.page} of ${pages}`);document.querySelector('#driftPrev').disabled=driftState.page<=1;document.querySelector('#driftNext').disabled=driftState.page>=pages}
function selectDriftEvent(item){if(!item)return;driftState.selected=item;renderDriftRows();setText('#driftDetailTitle',item.dataset_name);setText('#driftDetailStatus',titleCase(item.status));document.querySelector('#driftDetailStatus').className=`status-badge drift-status-chip ${item.status}`;document.querySelector('#driftDetailBody').innerHTML=`<div class="drift-detail-grid"><div><span>Versions</span><strong>v${item.baseline_version} \u2192 v${item.candidate_version}</strong></div><div><span>Detected</span><strong>${new Date(item.detected_at).toLocaleString()}</strong></div><div><span>Drift type</span><strong>${escapeHtml(driftLabel(item.drift_type))}</strong></div><div><span>Impact score</span><strong>${item.impact_score}/100 \u00b7 ${escapeHtml(titleCase(item.severity))}</strong></div></div><p class="drift-description">${escapeHtml(item.description)}</p><div><p class="eyebrow">Affected columns (${item.affected_columns.length})</p><div class="drift-column-list">${item.affected_columns.map(c=>`<div class="drift-column-item"><strong>${escapeHtml(c.name)}</strong><small>${escapeHtml(String(c.before??'Not present'))} \u2192 ${escapeHtml(String(c.after??'Not present'))}</small></div>`).join('')}</div></div>`;document.querySelector('#driftViewVersions').disabled=false;document.querySelector('#driftOpenAudit').disabled=false}
function clearDriftDetail(){driftState.selected=null;setText('#driftDetailTitle','Select an event');setText('#driftDetailStatus','\u2014');document.querySelector('#driftDetailBody').innerHTML='Choose a drift event to inspect affected columns, severity, impact, and linked versions.';document.querySelector('#driftViewVersions').disabled=true;document.querySelector('#driftOpenAudit').disabled=true}
function resetDriftFilters(){document.querySelector('#driftSearch').value='';document.querySelector('#driftDatasetFilter').value='all';document.querySelector('#driftTypeFilter').value='all';document.querySelector('#driftSeverityFilter').value='all';document.querySelector('#driftStatusFilter').value='all';loadSchemaDrift()}
async function exportDriftReport(){const response=await fetch('/schema-drift/export');if(!response.ok)return setStatus('Unable to export schema drift report.');const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='schema_drift_report.csv';a.click();URL.revokeObjectURL(url);setStatus('Schema drift report exported.')}
function viewDriftInVersions(){const item=driftState.selected;if(!item)return;navigateToPage('versions');const select=document.querySelector('#versionDatasetSelect');select.value=String(item.dataset_id);loadDatasetVersions(item.dataset_id).then(()=>{document.querySelector('#baselineVersionSelect').value=item.baseline_audit_id;document.querySelector('#candidateVersionSelect').value=item.candidate_audit_id;compareDatasetVersions()})}
function openDriftAudit(){const item=driftState.selected;if(!item)return;navigateToPage('audit');const url=new URL(location.href);url.searchParams.set('audit',item.candidate_audit_id);history.replaceState({page:'audit'},'',url);loadAuditByIdV2(item.candidate_audit_id)}
let driftSearchTimer;document.querySelector('#driftSearch')?.addEventListener('input',()=>{clearTimeout(driftSearchTimer);driftSearchTimer=setTimeout(loadSchemaDrift,250)});['driftDatasetFilter','driftTypeFilter','driftSeverityFilter','driftStatusFilter'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('change',loadSchemaDrift));document.querySelector('#resetDriftFilters')?.addEventListener('click',resetDriftFilters);document.querySelector('#refreshDriftButton')?.addEventListener('click',loadSchemaDrift);document.querySelector('#exportDriftButton')?.addEventListener('click',exportDriftReport);document.querySelector('#driftPrev')?.addEventListener('click',()=>{driftState.page--;renderDriftRows()});document.querySelector('#driftNext')?.addEventListener('click',()=>{driftState.page++;renderDriftRows()});document.querySelector('#driftViewVersions')?.addEventListener('click',viewDriftInVersions);document.querySelector('#driftOpenAudit')?.addEventListener('click',openDriftAudit);

const scheduleState = { payload: null, scoreChart: null, executionChart: null, failureChart: null, pendingDeleteId: null, calendarDate: new Date() };

const scheduleIcons = {
  run: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10-6.5z" fill="currentColor"/></svg>',
  pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3v14H7zm7 0h3v14h-3z" fill="currentColor"/></svg>',
  more: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="1.8" fill="currentColor"/><circle cx="12" cy="12" r="1.8" fill="currentColor"/><circle cx="12" cy="19" r="1.8" fill="currentColor"/></svg>',
  delete: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 8v10m4-10v10m4-10v10M5 6h14M9 6l1-2h4l1 2m-8 0 1 14h8l1-14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  dataset: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5" rx="7" ry="3" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>'
};

async function openSchedulesPage() {
  authEls.profileMenu.classList.add("hidden");
  hideAllPages();
  animatePage(document.querySelector("#schedulesPage"));
  document.querySelector("#schedulesNavButton")?.classList.add("active");
  const title=document.querySelector('#topbarPageTitle'); if(title) title.textContent='Scheduled Audits & Monitoring';
  const crumb=document.querySelector('#topbarBreadcrumb'); if(crumb) crumb.textContent='Home / Monitoring / Scheduled Audits';
  await loadSchedules();
}

function scheduleTimeLabel(item){return `${String(item.hour).padStart(2,'0')}:${String(item.minute).padStart(2,'0')}`;}
function scheduleFrequencyTitle(item){
  if(item.frequency==='weekly') return `Weekly \u00b7 ${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][item.day_of_week ?? 0]}`;
  if(item.frequency==='monthly') return `Monthly \u00b7 Day ${item.day_of_month || 1}`;
  return 'Daily';
}
function scheduleFrequencyLabel(item) { return `${scheduleFrequencyTitle(item)} \u00b7 ${scheduleTimeLabel(item)}`; }
function dateParts(value){
  if(!value)return {primary:'\u2014',secondary:'No run'};
  const dt=new Date(value);
  return {primary:dt.toLocaleDateString([],{month:'short',day:'numeric',year:'numeric'}),secondary:dt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false})};
}
function compactDate(value){ if(!value)return '\u2014'; return new Date(value).toLocaleString([], {month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'}); }
function durationLabel(ms){ if(ms==null)return '\u2014'; const sec=Math.round(ms/1000); return sec<60?`00:00:${String(sec).padStart(2,'0')}`:`00:${String(Math.floor(sec/60)).padStart(2,'0')}:${String(sec%60).padStart(2,'0')}`; }

// Compatibility marker retained for regression coverage: fetch('/schedules')
async function loadSchedules() {
  const rows=document.querySelector('#scheduleRows'); if(rows) rows.innerHTML='<div class="ui-loading-state"><span class="ui-spinner"></span><span>Loading schedules\u2026</span></div>';
  const response=await fetch(`/schedules?timezone_offset_minutes=${new Date().getTimezoneOffset()}`); const payload=await response.json().catch(()=>({}));
  if(!response.ok){ if(rows)rows.innerHTML=`<div class="schedule-empty error">${escapeHtml(payload.detail||'Unable to load schedules.')}</div>`; return; }
  scheduleState.payload=payload; renderSchedules(payload);
}
function renderSchedules(payload){
  setText('#scheduleTotal',payload.metrics.total); setText('#scheduleActive',payload.metrics.active); setText('#scheduleCompleted',payload.metrics.completed_7d); setText('#scheduleFailed',payload.metrics.failed_7d);
  if(payload.metrics.next_run_at){const dt=new Date(payload.metrics.next_run_at);setText('#scheduleNext',dt.toLocaleDateString([],{month:'short',day:'numeric',year:'numeric'}));setText('#scheduleNextTime',dt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false}));}else{setText('#scheduleNext','\u2014');setText('#scheduleNextTime','No upcoming run');}
  const target=document.querySelector('#scheduleRows');
  target.innerHTML=payload.schedules.length?payload.schedules.map(item=>{
    const next=dateParts(item.next_run_at), last=dateParts(item.last_run_at);
    return `<div class="schedule-row">
      <span class="schedule-dataset"><i>${scheduleIcons.dataset}</i><b title="${escapeHtml(item.dataset_name)}">${escapeHtml(item.dataset_name)}</b><small>${escapeHtml(item.name||item.source_type||'Dataset')}</small></span>
      <span class="schedule-cell-stack"><b>${escapeHtml(scheduleFrequencyTitle(item))}</b><small>${escapeHtml(scheduleTimeLabel(item))}</small></span>
      <span class="schedule-cell-stack"><b>${escapeHtml(next.primary)}</b><small>${escapeHtml(next.secondary)}</small></span>
      <span class="schedule-cell-stack"><b>${escapeHtml(last.primary)}</b><small>${escapeHtml(last.secondary)}</small></span>
      <span><em class="schedule-status ${item.status}">${escapeHtml(titleCase(item.status))}</em></span>
      <span class="schedule-result">${item.score==null?'<small>No runs yet</small>':`<b class="schedule-score">${item.score}</b><small>${item.issue_count} issues</small>`}</span>
      <span class="schedule-actions"><button class="schedule-action-button" data-schedule-run="${item.id}" title="Run now" aria-label="Run now">${scheduleIcons.run}</button><button class="schedule-action-button" data-schedule-toggle="${item.id}" data-status="${item.status}" title="${item.status==='active'?'Pause':'Resume'}" aria-label="${item.status==='active'?'Pause':'Resume'}">${item.status==='active'?scheduleIcons.pause:scheduleIcons.run}</button><button class="schedule-action-button" data-schedule-delete="${item.id}" title="Delete schedule" aria-label="Delete schedule">${scheduleIcons.delete}</button></span>
    </div>`;
  }).join(''):'<div class="schedule-empty"><strong>No schedules yet</strong><span>Create the first automated audit schedule.</span></div>';
  target.querySelectorAll('[data-schedule-run]').forEach(b=>b.onclick=()=>runScheduleNow(Number(b.dataset.scheduleRun)));
  target.querySelectorAll('[data-schedule-toggle]').forEach(b=>b.onclick=()=>toggleSchedule(Number(b.dataset.scheduleToggle),b.dataset.status));
  target.querySelectorAll('[data-schedule-delete]').forEach(b=>b.onclick=()=>deleteSchedule(Number(b.dataset.scheduleDelete)));
  const upcoming=document.querySelector('#upcomingScheduleRows'); upcoming.innerHTML=payload.upcoming.length?payload.upcoming.map(item=>`<div class="upcoming-row"><time><b>${new Date(item.next_run_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false})}</b><small>${new Date(item.next_run_at).toLocaleDateString([],{month:'short',day:'numeric'})}</small></time><i>${scheduleIcons.dataset}</i><span><b>${escapeHtml(item.dataset_name)}</b><small>${escapeHtml(titleCase(item.frequency))}</small></span></div>`).join(''):'<div class="schedule-empty">No upcoming runs.</div>';
  const runTarget=document.querySelector('#scheduleRunRows'); runTarget.innerHTML=payload.runs.length?payload.runs.map(run=>`<div class="schedule-run-row"><span><b>${escapeHtml(run.dataset_name)}</b></span><span>${compactDate(run.started_at)}</span><span>${durationLabel(run.duration_ms)}</span><span><em class="run-status ${run.status}">${escapeHtml(titleCase(run.status))}</em></span><span>${run.score??'\u2014'}</span><span>${run.issue_count??'\u2014'}</span><span>${escapeHtml(titleCase(run.triggered_by))}</span><span>${run.audit_id?`<button data-open-scheduled-audit="${run.audit_id}" class="secondary-button">View Audit</button>`:'\u2014'}</span></div>`).join(''):'<div class="schedule-empty">No scheduled audit runs yet.</div>';
  runTarget.querySelectorAll('[data-open-scheduled-audit]').forEach(b=>b.onclick=async()=>{await openAudit(b.dataset.openScheduledAudit);navigateToPage('audit')});
  renderScheduleCharts(payload.runs);
}
function renderScheduleCharts(runs){
  const completed=runs.filter(x=>x.status==='completed').slice().reverse(); const labels=completed.map(x=>new Date(x.started_at).toLocaleDateString([],{month:'short',day:'numeric'}));
  for(const c of ['scoreChart','executionChart','failureChart']) scheduleState[c]?.destroy();
  const scoreCtx=document.querySelector('#scheduleScoreChart'); if(scoreCtx) scheduleState.scoreChart=new Chart(scoreCtx,{type:'line',data:{labels,datasets:[{label:'Reliability score',data:completed.map(x=>x.score),tension:.35,fill:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:100}}}});
  const statuses=['completed','failed','in_progress','skipped']; const counts=statuses.map(s=>runs.filter(x=>x.status===s).length); const execCtx=document.querySelector('#scheduleExecutionChart'); if(execCtx) scheduleState.executionChart=new Chart(execCtx,{type:'doughnut',data:{labels:statuses.map(titleCase),datasets:[{data:counts}]},options:{responsive:true,maintainAspectRatio:false,cutout:'68%'}});
  const failCtx=document.querySelector('#scheduleFailureChart'); if(failCtx) scheduleState.failureChart=new Chart(failCtx,{type:'bar',data:{labels:labels.slice(-7),datasets:[{label:'Issues',data:completed.slice(-7).map(x=>x.issue_count||0)}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}});
}
async function populateScheduleDatasets(){const response=await fetch('/datasets');const data=await response.json().catch(()=>[]);const select=document.querySelector('#scheduleDataset');select.innerHTML=(Array.isArray(data)?data:[]).map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');}
async function openScheduleDialog(){await populateScheduleDatasets();const error=document.querySelector('#scheduleFormError');error.textContent='';error.classList.add('hidden');document.querySelector('#scheduleDialog').showModal();}
function updateScheduleFields(){const f=document.querySelector('#scheduleFrequency').value;document.querySelector('#scheduleWeekdayWrap').classList.toggle('hidden',f!=='weekly');document.querySelector('#scheduleMonthdayWrap').classList.toggle('hidden',f!=='monthly');}
async function createSchedule(event){event.preventDefault();const [hour,minute]=document.querySelector('#scheduleTime').value.split(':').map(Number);const frequency=document.querySelector('#scheduleFrequency').value;const body={dataset_id:Number(document.querySelector('#scheduleDataset').value),name:document.querySelector('#scheduleName').value||null,frequency,hour,minute,timezone_offset_minutes:new Date().getTimezoneOffset(),day_of_week:frequency==='weekly'?Number(document.querySelector('#scheduleWeekday').value):null,day_of_month:frequency==='monthly'?Number(document.querySelector('#scheduleMonthday').value):null};const response=await fetch('/schedules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const payload=await response.json().catch(()=>({}));if(!response.ok){const error=document.querySelector('#scheduleFormError');error.textContent=payload.detail||'Unable to create schedule.';error.classList.remove('hidden');return;}document.querySelector('#scheduleDialog').close();setStatus('Audit schedule created.');await loadSchedules();}
async function runScheduleNow(id){setStatus('Queueing scheduled audit\u2026');const r=await fetch(`/schedules/${id}/run`,{method:'POST'});const p=await r.json().catch(()=>({}));if(!r.ok){setStatus(p.detail||'Scheduled audit could not be queued.');return;}const job=p.job;setStatus(`Scheduled audit queued as job #${job.id}.`);try{const result=await pollBackgroundJob(job.id);setStatus(`Scheduled audit completed with score ${result.score}.`);}catch(error){setStatus(error.message||'Scheduled audit failed.');}await loadSchedules();}
async function toggleSchedule(id,current){const status=current==='active'?'paused':'active';await fetch(`/schedules/${id}/status`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});await loadSchedules();}

function scheduleOccurrencesForMonth(item, monthDate){
  const year=monthDate.getFullYear(), month=monthDate.getMonth();
  const days=new Date(year,month+1,0).getDate();
  const occurrences=[];
  for(let day=1;day<=days;day++){
    const date=new Date(year,month,day,item.hour,item.minute,0,0);
    let match=item.frequency==='daily';
    if(item.frequency==='weekly') match=((date.getDay()+6)%7)===(item.day_of_week??0);
    if(item.frequency==='monthly') match=day===(item.day_of_month||1);
    if(match) occurrences.push({...item,occurrence_at:date});
  }
  return occurrences;
}
function renderScheduleCalendar(){
  const body=document.querySelector('#scheduleCalendarBody');
  const monthDate=scheduleState.calendarDate;
  setText('#scheduleCalendarMonth',monthDate.toLocaleDateString([],{month:'long',year:'numeric'}));
  const year=monthDate.getFullYear(), month=monthDate.getMonth();
  const firstDay=new Date(year,month,1).getDay();
  const days=new Date(year,month+1,0).getDate();
  const active=(scheduleState.payload?.schedules||[]).filter(x=>x.status==='active');
  const byDay=new Map();
  active.flatMap(item=>scheduleOccurrencesForMonth(item,monthDate)).forEach(item=>{const day=item.occurrence_at.getDate();if(!byDay.has(day))byDay.set(day,[]);byDay.get(day).push(item)});
  const cells=[];
  for(let i=0;i<firstDay;i++)cells.push('<div class="calendar-day calendar-day-empty" aria-hidden="true"></div>');
  const today=new Date();
  for(let day=1;day<=days;day++){
    const events=byDay.get(day)||[];
    const isToday=today.getFullYear()===year&&today.getMonth()===month&&today.getDate()===day;
    const eventHtml=events.slice(0,2).map(e=>`<span class="calendar-event-dot">${escapeHtml(scheduleTimeLabel(e))} ${escapeHtml(e.dataset_name)}</span>`).join('');
    cells.push(`<button type="button" class="calendar-day ${events.length?'has-runs':''} ${isToday?'today':''}" data-calendar-day="${day}" aria-label="${day}, ${events.length} scheduled runs"><span class="calendar-day-number">${day}</span>${eventHtml}${events.length>2?`<small>+${events.length-2} more</small>`:''}</button>`);
  }
  body.innerHTML=cells.join('');
  body.querySelectorAll('[data-calendar-day]').forEach(cell=>{
    const events=byDay.get(Number(cell.dataset.calendarDay))||[];
    if(!events.length)return;
    cell.addEventListener('mouseenter',event=>showScheduleCalendarTooltip(event,events));
    cell.addEventListener('focus',event=>showScheduleCalendarTooltip(event,events));
    cell.addEventListener('mouseleave',hideScheduleCalendarTooltip);
    cell.addEventListener('blur',hideScheduleCalendarTooltip);
  });
}
function showScheduleCalendarTooltip(event,items){
  const tooltip=document.querySelector('#scheduleCalendarTooltip');
  tooltip.innerHTML=`<strong>${items[0].occurrence_at.toLocaleDateString([],{weekday:'long',month:'long',day:'numeric'})}</strong>${items.map(item=>`<div><time>${escapeHtml(scheduleTimeLabel(item))}</time><span>${escapeHtml(item.dataset_name)}<small>${escapeHtml(scheduleFrequencyTitle(item))}</small></span></div>`).join('')}`;
  const dialog=document.querySelector('#scheduleCalendarDialog');const rect=event.currentTarget.getBoundingClientRect();const dialogRect=dialog.getBoundingClientRect();
  tooltip.style.left=`${Math.min(rect.left-dialogRect.left,dialogRect.width-290)}px`;tooltip.style.top=`${rect.bottom-dialogRect.top+8}px`;tooltip.classList.remove('hidden');
}
function hideScheduleCalendarTooltip(){document.querySelector('#scheduleCalendarTooltip')?.classList.add('hidden');}
function openScheduleCalendar(){
  scheduleState.calendarDate=new Date();scheduleState.calendarDate.setDate(1);
  renderScheduleCalendar();document.querySelector('#scheduleCalendarDialog')?.showModal();
}
function moveScheduleCalendarMonth(offset){scheduleState.calendarDate=new Date(scheduleState.calendarDate.getFullYear(),scheduleState.calendarDate.getMonth()+offset,1);hideScheduleCalendarTooltip();renderScheduleCalendar();}
function closeScheduleCalendar(){hideScheduleCalendarTooltip();document.querySelector('#scheduleCalendarDialog')?.close();}
function deleteSchedule(id){
  scheduleState.pendingDeleteId=id;
  const item=scheduleState.payload?.schedules?.find(x=>Number(x.id)===Number(id));
  setText('#deleteScheduleDescription',item?`Delete ${item.name||item.dataset_name}? Existing audit history will remain available.`:'This removes the recurring schedule. Existing audit history remains available.');
  document.querySelector('#deleteScheduleDialog')?.showModal();
}
function closeDeleteScheduleDialog(){scheduleState.pendingDeleteId=null;document.querySelector('#deleteScheduleDialog')?.close();}
async function confirmDeleteSchedule(){
  const id=scheduleState.pendingDeleteId;if(!id)return;
  const button=document.querySelector('#confirmDeleteSchedule');button.disabled=true;button.textContent='Deleting\u2026';
  const response=await fetch(`/schedules/${id}`,{method:'DELETE'});const payload=await response.json().catch(()=>({}));
  button.disabled=false;button.textContent='Delete schedule';
  if(!response.ok){setStatus(payload.detail||'Unable to delete audit schedule.');return;}
  closeDeleteScheduleDialog();setStatus('Audit schedule deleted.');await loadSchedules();
}

document.querySelector('#newScheduleButton')?.addEventListener('click',openScheduleDialog);
document.querySelector('#refreshSchedulesButton')?.addEventListener('click',loadSchedules);
document.querySelector('#viewScheduleCalendar')?.addEventListener('click',openScheduleCalendar);
document.querySelector('#closeScheduleCalendar')?.addEventListener('click',closeScheduleCalendar);
document.querySelector('#closeScheduleCalendarFooter')?.addEventListener('click',closeScheduleCalendar);
document.querySelector('#scheduleCalendarPrevious')?.addEventListener('click',()=>moveScheduleCalendarMonth(-1));
document.querySelector('#scheduleCalendarNext')?.addEventListener('click',()=>moveScheduleCalendarMonth(1));
document.querySelector('#scheduleFrequency')?.addEventListener('change',updateScheduleFields);
document.querySelector('#scheduleForm')?.addEventListener('submit',createSchedule);
document.querySelector('#closeScheduleDialog')?.addEventListener('click',()=>document.querySelector('#scheduleDialog').close());
document.querySelector('#cancelScheduleDialog')?.addEventListener('click',()=>document.querySelector('#scheduleDialog').close());
document.querySelector('#closeDeleteScheduleDialog')?.addEventListener('click',closeDeleteScheduleDialog);
document.querySelector('#cancelDeleteSchedule')?.addEventListener('click',closeDeleteScheduleDialog);
document.querySelector('#confirmDeleteSchedule')?.addEventListener('click',confirmDeleteSchedule);



const connectorState={page:1,payload:null,selected:null,searchTimer:null,deleteId:null};
const connectorIcons={
  BigQuery:`<svg viewBox="0 0 24 24"><path d="M5 5h10l4 7-4 7H5l-4-7 4-7Z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="10" cy="12" r="2.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="m12 14 3 3" stroke="currentColor" stroke-width="1.5"/></svg>`,
  PostgreSQL:`<svg viewBox="0 0 24 24"><path d="M7 18c-2-2-3-5-2-9 1-4 4-6 7-6s6 2 7 6c1 4 0 7-2 9M9 10v9m6-9v9M8 14h8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`,
  MySQL:`<svg viewBox="0 0 24 24"><path d="M4 15c3-6 8-9 16-7-3 1-5 3-6 6 2 0 4 .5 6 2-5 1-10 1-16-1Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`,
  'Google Sheets':`<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6V3Z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M14 3v5h4M9 11h6M9 15h6M9 19h6" stroke="currentColor" stroke-width="1.4"/></svg>`,
  'Google Cloud Storage':`<svg viewBox="0 0 24 24"><path d="M7 18h10a4 4 0 0 0 .7-7.9A6 6 0 0 0 6.4 9 4.5 4.5 0 0 0 7 18Z" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`,
  'REST API':`<svg viewBox="0 0 24 24"><path d="M8 7H5a3 3 0 0 0-3 3v4a3 3 0 0 0 3 3h3m8-10h3a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3h-3M8 12h8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`
};
const actionSvgs={play:`<svg viewBox="0 0 24 24"><path d="m8 5 11 7-11 7V5Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>`,more:`<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>`,test:`<svg viewBox="0 0 24 24"><path d="M4 12h3l2-5 4 10 2-5h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,sync:`<svg viewBox="0 0 24 24"><path d="M20 6v5h-5M4 18v-5h5M6.1 9A7 7 0 0 1 18 6l2 5M17.9 15A7 7 0 0 1 6 18l-2-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,edit:`<svg viewBox="0 0 24 24"><path d="m4 16-1 5 5-1L19 9l-4-4L4 16Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m13 7 4 4" stroke="currentColor" stroke-width="1.7"/></svg>`,trash:`<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3m-9 0 1 14h10l1-14M10 11v6m4-6v6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>`};
async function openConnectorsPage(){authEls.profileMenu.classList.add('hidden');hideAllPages();animatePage(document.querySelector('#connectorsPage'));document.querySelector('#connectorsNavButton')?.classList.add('active');setText('#topbarPageTitle','Connectors');setText('#topbarBreadcrumb','Home / Data Management / Connectors');await loadConnectors();}
function connectorQuery(){const q=new URLSearchParams({page:String(connectorState.page),page_size:'5'}),search=document.querySelector('#connectorSearch')?.value.trim(),status=document.querySelector('#connectorStatus')?.value,type=document.querySelector('#connectorSourceType')?.value;if(search)q.set('search',search);if(status&&status!=='all')q.set('status',status);if(type&&type!=='all')q.set('source_type',type);return q.toString()}
async function loadConnectors(){const rows=document.querySelector('#connectorRows');if(rows)rows.innerHTML='<div class="ui-loading-state"><span class="ui-spinner"></span><span>Loading connectors\u2026</span></div>';const r=await fetch(`/connectors?${connectorQuery()}`),p=await r.json().catch(()=>({}));if(!r.ok){if(rows)rows.innerHTML=`<div class="empty-row error">${escapeHtml(p.detail||'Unable to load connectors.')}</div>`;return}connectorState.payload=p;renderConnectors()}
function connectorSourceClassName(sourceType){return String(sourceType||'').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'')}
function renderConnectors(){const p=connectorState.payload||{},m=p.metrics||{};setText('#connectorTotal',m.total||0);setText('#connectorActive',m.active||0);setText('#connectorInactive',m.inactive||0);setText('#connectorFailed',m.failed||0);setText('#connectorSources',m.source_types||0);const type=document.querySelector('#connectorSourceType'),current=type.value;type.innerHTML='<option value="all">All</option>'+(p.source_types||[]).map(x=>`<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join('');type.value=current||'all';const rows=document.querySelector('#connectorRows'),items=p.connectors||[];rows.innerHTML=items.length?items.map(c=>`<div class="connector-row ${connectorState.selected?.id===c.id?'selected':''}" data-connector-id="${c.id}"><span class="connector-name-cell"><i class="connector-source-icon ${connectorSourceClassName(c.source_type)}">${connectorIcons[c.source_type]||connectorIcons['REST API']}</i><span><strong>${escapeHtml(c.name)}</strong><small>${escapeHtml(c.configuration?.dataset_name||'Connected source')}</small></span></span><span>${escapeHtml(c.source_type)}</span><span class="truncate-cell">${escapeHtml(c.host_project||'\u2014')}</span><span><i class="connector-status ${c.status} ${c.status==='failed'?'failed':''}">${escapeHtml(c.status==='failed'?'Failed':titleCase(c.status))}</i></span><span>${c.last_sync_at?`${new Date(c.last_sync_at).toLocaleDateString()}<small>${new Date(c.last_sync_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</small>`:'\u2014<small>No sync</small>'}</span><span class="connector-row-actions"><button type="button" data-connector-test="${c.id}" aria-label="Test connector" title="Test connection">${actionSvgs.test}</button><button type="button" data-connector-sync="${c.id}" aria-label="Sync connector" title="Sync now">${actionSvgs.sync}</button><button type="button" data-connector-menu="${c.id}" aria-label="Connector details" title="Open details">${actionSvgs.more}</button></span></div>`).join(''):'<div class="empty-row">No connectors match the current filters.</div>';rows.querySelectorAll('[data-connector-id]').forEach(row=>row.onclick=e=>{if(e.target.closest('button'))return;selectConnector(Number(row.dataset.connectorId))});rows.querySelectorAll('[data-connector-test]').forEach(b=>b.onclick=()=>testConnector(Number(b.dataset.connectorTest)));rows.querySelectorAll('[data-connector-sync]').forEach(b=>b.onclick=()=>syncConnector(Number(b.dataset.connectorSync)));rows.querySelectorAll('[data-connector-menu]').forEach(b=>b.onclick=()=>selectConnector(Number(b.dataset.connectorMenu)));const pg=p.pagination||{page:1,page_size:Math.max(items.length,1),total:items.length,pages:1};setText('#connectorPageSummary',`Showing ${items.length?((pg.page-1)*pg.page_size)+1:0} to ${Math.min((pg.page||1)*(pg.page_size||5),pg.total||0)} of ${pg.total||0} connectors`);setText('#connectorPageNumber',`Page ${pg.page||1} of ${pg.pages||1}`);document.querySelector('#connectorPreviousPage').disabled=(pg.page||1)<=1;document.querySelector('#connectorNextPage').disabled=(pg.page||1)>=(pg.pages||1);if(connectorState.selected){const fresh=items.find(x=>x.id===connectorState.selected.id);if(fresh)selectConnector(fresh.id)}}
function selectConnector(id){const item=(connectorState.payload?.connectors||[]).find(x=>x.id===id);if(!item)return;connectorState.selected=item;document.querySelectorAll('.connector-row').forEach(r=>r.classList.toggle('selected',Number(r.dataset.connectorId)===id));renderConnectorDetail(item)}
function renderConnectorDetail(c){const health=c.status==='healthy'?'Healthy':c.status==='failed'?'Failed':'Not tested';document.querySelector('#connectorDetailPanel').innerHTML=`<div class="connector-detail-header"><div class="connector-detail-title"><i class="connector-source-icon ${connectorSourceClassName(c.source_type)}">${connectorIcons[c.source_type]||connectorIcons['REST API']}</i><div><h2>${escapeHtml(c.name)}</h2><i class="connector-status ${c.status}">${titleCase(c.status)}</i></div></div><button id="closeConnectorDetail" class="icon-button" type="button" aria-label="Close connector detail">\u00d7</button></div><div class="connector-detail-tabs" role="tablist"><button type="button" class="active">Overview</button><button type="button">Schema</button><button type="button">Activity</button><button type="button">Settings</button></div><dl class="connector-detail-meta"><div><dt>Source Type</dt><dd>${escapeHtml(c.source_type)}</dd></div><div><dt>Host / Project</dt><dd>${escapeHtml(c.host_project||'\u2014')}</dd></div><div><dt>Dataset</dt><dd>${escapeHtml(c.configuration?.dataset_name||'Not assigned')}</dd></div><div><dt>Last Sync</dt><dd>${c.last_sync_at?new Date(c.last_sync_at).toLocaleString():'Never'}</dd></div><div><dt>Last Test</dt><dd>${c.last_tested_at?new Date(c.last_tested_at).toLocaleString():'Never'}</dd></div></dl><div class="connector-health-grid"><article><span>Health Status</span><strong class="health-${c.status}">${health}</strong><small>${escapeHtml(c.last_error||'Run a connection test')}</small></article><article><span>Sync Status</span><strong>${escapeHtml(titleCase(c.last_sync_status||'Not synced'))}</strong><small>${escapeHtml(c.last_error||'No sync history')}</small></article><article><span>Data Freshness</span><strong>${c.last_sync_at?relativeTime(c.last_sync_at):'\u2014'}</strong><small>Since last successful sync</small></article></div><div class="connector-detail-actions"><button id="testConnectorButton" class="secondary-button svg-button">${actionSvgs.test}Test connection</button><button id="syncConnectorButton" class="secondary-button svg-button">${actionSvgs.sync}Sync now</button><button id="editConnectorButton" class="secondary-button svg-button wide">${actionSvgs.edit}Edit connector</button><button id="deleteConnectorButton" class="secondary-button svg-button danger-outline wide">${actionSvgs.trash}Delete connector</button></div>`;document.querySelector('#closeConnectorDetail').onclick=clearConnectorDetail;document.querySelector('#testConnectorButton').onclick=()=>testConnector(c.id);document.querySelector('#syncConnectorButton').onclick=()=>syncConnector(c.id);document.querySelector('#editConnectorButton').onclick=()=>openConnectorDialog(c);document.querySelector('#deleteConnectorButton').onclick=()=>openDeleteConnector(c)}
function clearConnectorDetail(){connectorState.selected=null;document.querySelector('#connectorDetailPanel').innerHTML='<div class="empty-detail"><h2>Select a connector</h2><p>Review configuration, health, activity, and sync controls.</p></div>';document.querySelectorAll('.connector-row').forEach(r=>r.classList.remove('selected'))}
function defaultConnectorConfig(type){return ({BigQuery:{project_id:'',dataset:'',dataset_name:''},PostgreSQL:{host:'',port:5432,database:'',username:'',dataset_name:''},MySQL:{host:'',port:3306,database:'',username:'',dataset_name:''},'Google Sheets':{spreadsheet_url:'',dataset_name:''},'Google Cloud Storage':{bucket:'',prefix:'',dataset_name:''},'REST API':{base_url:'',method:'GET',dataset_name:''}})[type]||{}}
function openConnectorDialog(item=null){document.querySelector('#connectorDialogTitle').textContent=item?'Edit Connector':'New Connector';document.querySelector('#connectorId').value=item?.id||'';document.querySelector('#connectorName').value=item?.name||'';document.querySelector('#connectorType').value=item?.source_type||'BigQuery';document.querySelector('#connectorHost').value=item?.host_project||'';document.querySelector('#connectorDatasetName').value=item?.configuration?.dataset_name||'';document.querySelector('#connectorFormStatus').value=item?.status||'active';document.querySelector('#connectorConfig').value=JSON.stringify(item?.configuration||defaultConnectorConfig(item?.source_type||'BigQuery'),null,2);document.querySelector('#connectorFormError').classList.add('hidden');document.querySelector('#connectorDialog').showModal()}
async function saveConnector(e){e.preventDefault();const error=document.querySelector('#connectorFormError');error.classList.add('hidden');let config;try{config=JSON.parse(document.querySelector('#connectorConfig').value||'{}')}catch{error.textContent='Configuration must be valid JSON.';error.classList.remove('hidden');return}const id=document.querySelector('#connectorId').value,body={name:document.querySelector('#connectorName').value,source_type:document.querySelector('#connectorType').value,host_project:document.querySelector('#connectorHost').value,configuration:{...config,dataset_name:document.querySelector('#connectorDatasetName').value},credential_hint:null,status:document.querySelector('#connectorFormStatus').value};const r=await fetch(id?`/connectors/${id}`:'/connectors',{method:id?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),p=await r.json().catch(()=>({}));if(!r.ok){error.textContent=p.detail||'Unable to save connector.';error.classList.remove('hidden');return}document.querySelector('#connectorDialog').close();setStatus(id?'Connector updated.':'Connector created.');await loadConnectors();selectConnector(p.id)}
async function testConnector(id){setStatus('Testing connector\u2026');const r=await fetch(`/connectors/${id}/test`,{method:'POST'}),p=await r.json().catch(()=>({}));setStatus(p.message||p.detail||'Connection test completed.');await loadConnectors();const item=(connectorState.payload?.connectors||[]).find(x=>x.id===id);if(item)selectConnector(id)}
async function syncConnector(id){setStatus('Syncing connector\u2026');const r=await fetch(`/connectors/${id}/sync`,{method:'POST'}),p=await r.json().catch(()=>({}));setStatus(p.message||p.detail||(r.ok?'Connector sync completed.':'Connector sync failed.'));await loadConnectors();const item=(connectorState.payload?.connectors||[]).find(x=>x.id===id);if(item)selectConnector(id)}
function openDeleteConnector(c){connectorState.deleteId=c.id;setText('#deleteConnectorDescription',`Delete ${c.name}? This removes its configuration and sync history.`);document.querySelector('#deleteConnectorDialog').showModal()}
async function confirmDeleteConnector(){if(!connectorState.deleteId)return;const r=await fetch(`/connectors/${connectorState.deleteId}`,{method:'DELETE'});if(!r.ok)return setStatus('Unable to delete connector.');document.querySelector('#deleteConnectorDialog').close();connectorState.deleteId=null;clearConnectorDetail();setStatus('Connector deleted.');await loadConnectors()}
function exportConnectors(){const items=connectorState.payload?.connectors||[];const csv=['Connector Name,Source Type,Host or Project,Status,Health,Last Sync',...items.map(c=>[c.name,c.source_type,c.host_project,c.status,c.status,c.last_sync_at||''].map(v=>`"${String(v??'').replaceAll('"','""')}"`).join(','))].join('\n'),blob=new Blob([csv],{type:'text/csv'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='connectors.csv';a.click();URL.revokeObjectURL(url)}
document.querySelector('#newConnectorButton')?.addEventListener('click',()=>openConnectorDialog());document.querySelector('#refreshConnectorsButton')?.addEventListener('click',loadConnectors);document.querySelector('#connectorForm')?.addEventListener('submit',saveConnector);document.querySelector('#closeConnectorDialog')?.addEventListener('click',()=>document.querySelector('#connectorDialog').close());document.querySelector('#cancelConnectorDialog')?.addEventListener('click',()=>document.querySelector('#connectorDialog').close());document.querySelector('#connectorType')?.addEventListener('change',e=>document.querySelector('#connectorConfig').value=JSON.stringify(defaultConnectorConfig(e.target.value),null,2));document.querySelector('#connectorSearch')?.addEventListener('input',()=>{clearTimeout(connectorState.searchTimer);connectorState.searchTimer=setTimeout(()=>{connectorState.page=1;loadConnectors()},250)});['connectorStatus','connectorSourceType'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('change',()=>{connectorState.page=1;loadConnectors()}));document.querySelector('#connectorPreviousPage')?.addEventListener('click',()=>{connectorState.page--;loadConnectors()});document.querySelector('#connectorNextPage')?.addEventListener('click',()=>{connectorState.page++;loadConnectors()});document.querySelector('#exportConnectorsButton')?.addEventListener('click',exportConnectors);document.querySelector('#closeDeleteConnectorDialog')?.addEventListener('click',()=>document.querySelector('#deleteConnectorDialog').close());document.querySelector('#cancelDeleteConnector')?.addEventListener('click',()=>document.querySelector('#deleteConnectorDialog').close());document.querySelector('#confirmDeleteConnector')?.addEventListener('click',confirmDeleteConnector);

const alertState={payload:null,selected:null,page:1,pageSize:8,tab:'all',searchTimer:null};
const alertIcons={score:'\u25d4',high_severity_issue:'\u25b3',rule_failure:'\u25a4',contract_violation:'\u25a3',schema_drift:'\u21bb',scheduled_audit_failure:'\u25f7'};
async function openAlertsPage(){
  authEls.profileMenu.classList.add('hidden');hideAllPages();animatePage(document.querySelector('#alertsPage'));document.querySelector('#alertsNavButton')?.classList.add('active');
  const title=document.querySelector('#topbarPageTitle');if(title)title.textContent='Alerts & Notifications';const crumb=document.querySelector('#topbarBreadcrumb');if(crumb)crumb.textContent='Home / Automation / Alerts & Notifications';
  await loadAlerts();
}
function alertQuery(){const p=new URLSearchParams({page:String(alertState.page),page_size:String(alertState.pageSize)});const search=document.querySelector('#alertSearch')?.value.trim();const severity=document.querySelector('#alertSeverity')?.value;let status=document.querySelector('#alertStatus')?.value;const type=document.querySelector('#alertType')?.value;const dataset=document.querySelector('#alertDataset')?.value;if(alertState.tab!=='all')status=alertState.tab;if(search)p.set('search',search);if(severity&&severity!=='all')p.set('severity',severity);if(status&&status!=='all')p.set('status',status);if(type&&type!=='all')p.set('alert_type',type);if(dataset)p.set('dataset_id',dataset);return p;}
async function loadAlerts(){const target=document.querySelector('#alertRows');if(target)target.innerHTML='<div class="ui-loading-state"><span class="ui-spinner"></span><span>Loading alerts\u2026</span></div>';const response=await fetch(`/alerts?${alertQuery()}`);const payload=await response.json().catch(()=>({}));if(!response.ok){if(target)target.innerHTML=`<div class="empty-row error">${escapeHtml(payload.detail||'Unable to load alerts.')}</div>`;return;}alertState.payload=payload;renderAlerts();}
function renderAlerts(){const p=alertState.payload||{};const m=p.metrics||{};setText('#alertCritical',m.critical||0);setText('#alertHigh',m.high||0);setText('#alertUnread',m.unread||0);setText('#alertResolved',m.resolved||0);setText('#alertTotal',m.total||0);setText('#alertTabAll',m.total||0);setText('#alertTabUnread',m.unread||0);setText('#alertTabAcknowledged',m.acknowledged||0);setText('#alertTabResolved',m.resolved||0);setText('#alertTabDismissed',m.dismissed||0);setText('#alertsNavCount',m.unread||0);document.querySelector('#alertsNavCount')?.classList.toggle('hidden',!(m.unread||0));
 const ds=document.querySelector('#alertDataset');const current=ds.value;ds.innerHTML='<option value="">All</option>'+(p.datasets||[]).map(x=>`<option value="${x.id}">${escapeHtml(x.name)}</option>`).join('');ds.value=current;
 const rows=document.querySelector('#alertRows');rows.innerHTML=(p.alerts||[]).length?(p.alerts||[]).map(a=>`<div class="alert-row ${alertState.selected?.id===a.id?'selected':''}" data-alert-id="${a.id}"><span class="alert-main"><i class="alert-icon ${a.severity}">${alertIcons[a.alert_type]||'!'}</i><span><strong>${escapeHtml(a.title)}</strong><small>${escapeHtml(a.dataset_name||'Workspace alert')}</small><small>${escapeHtml(alertTypeLabel(a.alert_type))}</small></span></span><span><span class="severity-pill ${a.severity}">${escapeHtml(titleCase(a.severity))}</span></span><span><span class="status-pill ${a.status}">${escapeHtml(alertStatusLabel(a.status))}</span></span><span class="alert-time">${new Date(a.detected_at).toLocaleDateString()}<br>${new Date(a.detected_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span><span class="alert-row-actions"><button data-view-alert="${a.id}" aria-label="View alert">\u25c9</button><button data-alert-menu="${a.id}" aria-label="Alert actions">\u22ee</button></span></div>`).join(''):'<div class="empty-row">No alerts match the current filters.</div>';
 rows.querySelectorAll('[data-alert-id]').forEach(row=>row.addEventListener('click',e=>{if(e.target.closest('button'))return;selectAlert(Number(row.dataset.alertId))}));rows.querySelectorAll('[data-view-alert]').forEach(b=>b.onclick=()=>selectAlert(Number(b.dataset.viewAlert)));rows.querySelectorAll('[data-alert-menu]').forEach(b=>b.onclick=()=>quickAlertAction(Number(b.dataset.alertMenu)));
 const pg=p.pagination||{page:1,pages:1,total:0};setText('#alertPageSummary',`${pg.total||0} alerts`);setText('#alertPageNumber',`Page ${pg.page||1} of ${pg.pages||1}`);document.querySelector('#alertPreviousPage').disabled=(pg.page||1)<=1;document.querySelector('#alertNextPage').disabled=(pg.page||1)>=(pg.pages||1);
 if(alertState.selected){const fresh=(p.alerts||[]).find(x=>x.id===alertState.selected.id);if(fresh)selectAlert(fresh.id,false);}
}
function alertTypeLabel(v){return ({score_threshold:'Reliability score',high_severity_issue:'High severity issue',rule_failure:'Quality rule',contract_violation:'Data contract',schema_drift:'Schema drift',scheduled_audit_failure:'Scheduled audit'})[v]||titleCase(v)}
function alertStatusLabel(v){return v==='new'?'New':titleCase(v)}
function selectAlert(id,markRead=true){const item=(alertState.payload?.alerts||[]).find(x=>x.id===id);if(!item)return;alertState.selected=item;renderAlertDetail(item);document.querySelectorAll('.alert-row').forEach(r=>r.classList.toggle('selected',Number(r.dataset.alertId)===id));if(markRead&&item.status==='new')alertAction(id,'read',false)}
function renderAlertDetail(a){const ref=a.reference||{};document.querySelector('#alertDetailPanel').innerHTML=`<div class="alert-detail-header"><div><span class="severity-pill ${a.severity}">${escapeHtml(titleCase(a.severity))}</span><h2>${escapeHtml(a.title)}</h2><div class="alert-detail-id">Alert ID: ALT-${String(a.id).padStart(6,'0')}</div></div><button class="icon-button" id="closeAlertDetail">\u00d7</button></div><dl class="alert-detail-meta"><div><dt>Status</dt><dd><span class="status-pill ${a.status}">${escapeHtml(alertStatusLabel(a.status))}</span></dd></div><div><dt>Dataset</dt><dd>${escapeHtml(a.dataset_name||'Workspace')}</dd></div>${a.audit_id?`<div><dt>Audit</dt><dd>${escapeHtml(a.audit_id)}<br><button id="alertOpenAudit" class="auth-link" type="button">View audit \u2197</button></dd></div>`:''}<div><dt>Detected at</dt><dd>${new Date(a.detected_at).toLocaleString()}</dd></div>${ref.score!==undefined?`<div><dt>Reliability score</dt><dd>${ref.score} / 100</dd></div>`:''}${ref.threshold!==undefined?`<div><dt>Threshold</dt><dd>${ref.threshold}</dd></div>`:''}${ref.rule_name?`<div><dt>Rule</dt><dd>${escapeHtml(ref.rule_name)}</dd></div>`:''}</dl><section class="alert-detail-section"><h3>Description</h3><p>${escapeHtml(a.description)}</p></section>${a.potential_impact?`<section class="alert-detail-section"><h3>Potential impact</h3><p>${escapeHtml(a.potential_impact)}</p></section>`:''}<div class="alert-detail-actions">${a.status!=='acknowledged'&&a.status!=='resolved'?`<button data-detail-action="acknowledge" type="button">Acknowledge</button>`:''}${a.status!=='resolved'?`<button data-detail-action="resolve" class="secondary-button" type="button">Resolve</button>`:`<button data-detail-action="reopen" class="secondary-button" type="button">Reopen</button>`}<button data-detail-action="dismiss" class="secondary-button" type="button">Dismiss</button></div>`;document.querySelector('#closeAlertDetail').onclick=clearAlertDetail;document.querySelector('#alertOpenAudit')?.addEventListener('click',()=>openAlertAudit(a));document.querySelectorAll('[data-detail-action]').forEach(b=>b.onclick=()=>alertAction(a.id,b.dataset.detailAction));}
function clearAlertDetail(){alertState.selected=null;document.querySelector('#alertDetailPanel').innerHTML='<div class="empty-detail"><span>\u2667</span><h2>Select an alert</h2><p>Review evidence, references, and lifecycle actions.</p></div>';document.querySelectorAll('.alert-row').forEach(r=>r.classList.remove('selected'))}
async function alertAction(id,action,reload=true){const r=await fetch(`/alerts/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});const p=await r.json().catch(()=>({}));if(!r.ok)return setStatus(p.detail||'Unable to update alert.');if(reload){setStatus(`Alert ${action}d.`);await loadAlerts();const item=(alertState.payload?.alerts||[]).find(x=>x.id===id);if(item)selectAlert(id,false);}else{loadAlerts();}}
function quickAlertAction(id){selectAlert(id);}
function openAlertAudit(a){if(!a.audit_id)return;navigateToPage('audit');const url=new URL(location.href);url.searchParams.set('audit',a.audit_id);history.replaceState({page:'audit'},'',url);openAudit(a.audit_id)}
async function exportAlerts(){const r=await fetch('/alerts/export.csv');if(!r.ok)return setStatus('Unable to export alerts.');const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='alerts_report.csv';a.click();URL.revokeObjectURL(url)}
async function openAlertPreferences(){const r=await fetch('/alerts/preferences/me');const p=await r.json();document.querySelector('#alertScoreThreshold').value=p.score_threshold;document.querySelector('#alertInApp').checked=p.in_app_enabled;document.querySelector('#alertEmail').checked=p.email_enabled;document.querySelector('#alertCriticalEnabled').checked=p.critical_enabled;document.querySelector('#alertHighEnabled').checked=p.high_enabled;document.querySelector('#alertMediumEnabled').checked=p.medium_enabled;document.querySelector('#alertLowEnabled').checked=p.low_enabled;document.querySelector('#alertPreferencesDialog').showModal()}
async function saveAlertPreferences(e){e.preventDefault();const body={score_threshold:Number(document.querySelector('#alertScoreThreshold').value),in_app_enabled:document.querySelector('#alertInApp').checked,email_enabled:document.querySelector('#alertEmail').checked,critical_enabled:document.querySelector('#alertCriticalEnabled').checked,high_enabled:document.querySelector('#alertHighEnabled').checked,medium_enabled:document.querySelector('#alertMediumEnabled').checked,low_enabled:document.querySelector('#alertLowEnabled').checked};const r=await fetch('/alerts/preferences/me',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(r.ok){document.querySelector('#alertPreferencesDialog').close();setStatus('Alert preferences saved.');await loadAlerts();}}
['alertSeverity','alertStatus','alertType','alertDataset'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('change',()=>{alertState.page=1;loadAlerts()}));document.querySelector('#alertSearch')?.addEventListener('input',()=>{clearTimeout(alertState.searchTimer);alertState.searchTimer=setTimeout(()=>{alertState.page=1;loadAlerts()},250)});document.querySelectorAll('[data-alert-tab]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-alert-tab]').forEach(x=>x.classList.remove('active'));b.classList.add('active');alertState.tab=b.dataset.alertTab;alertState.page=1;loadAlerts()}));document.querySelector('#alertPreviousPage')?.addEventListener('click',()=>{alertState.page--;loadAlerts()});document.querySelector('#alertNextPage')?.addEventListener('click',()=>{alertState.page++;loadAlerts()});document.querySelector('#refreshAlertsButton')?.addEventListener('click',loadAlerts);document.querySelector('#exportAlertsButton')?.addEventListener('click',exportAlerts);document.querySelector('#alertPreferencesButton')?.addEventListener('click',openAlertPreferences);document.querySelector('#closeAlertPreferences')?.addEventListener('click',()=>document.querySelector('#alertPreferencesDialog').close());document.querySelector('#cancelAlertPreferences')?.addEventListener('click',()=>document.querySelector('#alertPreferencesDialog').close());document.querySelector('#alertPreferencesForm')?.addEventListener('submit',saveAlertPreferences);

// Feature 23: Reliability Copilot
const copilotState={context:null,sessionId:null,currentResponse:null,deleteSessionId:null};
const copilotEscape=value=>escapeHtml(String(value??''));
function copilotDate(value){return value?new Date(value).toLocaleString([], {month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'}):'\u2014'}
async function openCopilotPage(){authEls.profileMenu.classList.add('hidden');hideAllPages();animatePage(document.querySelector('#copilotPage'));document.querySelector('#copilotNavButton')?.classList.add('active');setText('#topbarPageTitle','Reliability Copilot');setText('#topbarBreadcrumb','Home / AI Assistance / Reliability Copilot');await loadCopilotContext()}
function copilotParams(){const params=new URLSearchParams();const datasetId=document.querySelector('#copilotDataset')?.value;const auditId=document.querySelector('#copilotAudit')?.value;const compareId=document.querySelector('#copilotCompare')?.value;if(datasetId)params.set('dataset_id',datasetId);if(auditId)params.set('audit_id',auditId);if(compareId)params.set('compare_audit_id',compareId);return params}
async function loadCopilotContext(){const r=await fetch(`/copilot/context?${copilotParams()}`),p=await r.json().catch(()=>({}));if(!r.ok){setStatus(p||'Unable to load Copilot context.');return}copilotState.context=p;renderCopilotContext(p);if(!copilotState.sessionId)await createCopilotSession(false)}
function renderCopilotContext(p){setText('#copilotWorkspace',document.querySelector('#workspaceSelect')?.selectedOptions?.[0]?.textContent?.trim()||'Current workspace');const ds=document.querySelector('#copilotDataset'),audit=document.querySelector('#copilotAudit'),compare=document.querySelector('#copilotCompare');const oldDs=ds.value,oldAudit=audit.value,oldCompare=compare.value,datasets=p.datasets||[],allAudits=p.audits||[];ds.innerHTML=datasets.length?datasets.map(x=>`<option value="${x.id}">${copilotEscape(x.name)}</option>`).join(''):'<option value="">No registered datasets</option>';const preferredDataset=oldDs||String(p.selected?.dataset?.id||datasets[0]?.id||'');if([...ds.options].some(o=>o.value===preferredDataset))ds.value=preferredDataset;ds.disabled=!datasets.length;const selectedDataset=datasets.find(x=>String(x.id)===ds.value);const audits=allAudits.filter(a=>!selectedDataset||a.dataset_name===selectedDataset.name);audit.innerHTML=audits.length?audits.map(a=>`<option value="${a.audit_id}">${copilotDate(a.created_at)} \u00b7 ${a.score}/100</option>`).join(''):'<option value="">No completed audits</option>';const preferredAudit=oldAudit||p.selected?.current?.audit_id||audits[0]?.audit_id||'';if([...audit.options].some(o=>o.value===preferredAudit))audit.value=preferredAudit;audit.disabled=!audits.length;compare.innerHTML='<option value="">No comparison</option>'+audits.filter(a=>a.audit_id!==audit.value).map(a=>`<option value="${a.audit_id}">${copilotDate(a.created_at)} \u00b7 ${a.score}/100</option>`).join('');if([...compare.options].some(o=>o.value===oldCompare))compare.value=oldCompare;compare.disabled=audits.length<2;renderCopilotSessions(p.sessions||[]);renderCopilotEvidence(p.selected||{});document.querySelector('#copilotSend').disabled=!datasets.length||!audits.length}
function renderCopilotSessions(items){const root=document.querySelector('#copilotSessionRows');root.innerHTML=items.length?items.slice(0,6).map(s=>`<div class="copilot-session-row ${s.id===copilotState.sessionId?'active':''}"><button type="button" class="copilot-session-open" data-copilot-session="${s.id}"><span class="copilot-session-icon">\u25b1</span><span class="copilot-session-copy"><strong>${copilotEscape(s.title)}</strong><small>${copilotDate(s.updated_at)}</small></span></button><button type="button" class="copilot-session-delete" data-delete-copilot-session="${s.id}" data-copilot-session-delete="${s.id}" data-session-title="${copilotEscape(s.title)}" aria-label="Delete ${copilotEscape(s.title)}" title="Delete session">${actionSvgs.trash}</button></div>`).join(''):'<div class="copilot-session-empty">No saved sessions yet.</div>';root.querySelectorAll('[data-copilot-session]').forEach(b=>b.onclick=()=>loadCopilotSession(Number(b.dataset.copilotSession)));root.querySelectorAll('[data-delete-copilot-session]').forEach(b=>b.onclick=e=>{e.stopPropagation();openDeleteCopilotSession(Number(b.dataset.deleteCopilotSession),b.dataset.sessionTitle)})}
function renderCopilotEvidence(ev){const c=ev.current||{},p=ev.previous||{},change=ev.score_change;const scoreClass=change==null?'neutral':change>=0?'positive':'negative';document.querySelector('#copilotEvidence').innerHTML=`<section class="copilot-score-card"><div><span>Reliability Score</span><strong>${c.score??'\u2014'}<small>/100</small></strong>${change!=null?`<b class="${scoreClass}">${change>0?'+':''}${change} pts</b>`:''}<small>${p.score!=null?`vs previous: ${p.score}/100`:'Latest completed audit'}</small></div><svg viewBox="0 0 160 54" aria-hidden="true"><polyline points="4,40 34,31 64,34 94,22 124,27 154,12" fill="none" stroke="currentColor" stroke-width="2"/></svg></section><section class="copilot-evidence-block"><span>Active Issues</span><strong>${c.issue_count??0}</strong><div class="copilot-severity-line"><b class="critical">${c.severity?.critical||0} Critical</b><b class="high">${c.severity?.high||0} High</b><b>${c.severity?.medium||0} Medium</b></div></section><section class="copilot-evidence-row"><span>Failed Rules</span><strong>${ev.failed_rules??c.failed_rules??0}</strong></section><section class="copilot-evidence-row"><span>Data Contract Violations</span><strong>${ev.contract_violations||0}</strong></section><section class="copilot-evidence-row"><span>Schema Drift Events</span><strong>${ev.drift_events||0}</strong></section><section class="copilot-columns"><span>Top Affected Columns</span><div>${(c.top_columns||[]).length?(c.top_columns||[]).map(x=>`<i>${copilotEscape(x)}</i>`).join(''):'<small>No affected columns identified</small>'}</div></section>`}
async function createCopilotSession(clear=true){const body={dataset_id:Number(document.querySelector('#copilotDataset')?.value)||null,audit_id:document.querySelector('#copilotAudit')?.value||null,compare_audit_id:document.querySelector('#copilotCompare')?.value||null,analysis_mode:document.querySelector('#copilotMode')?.value||'general'};const r=await fetch('/copilot/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),p=await r.json().catch(()=>({}));if(!r.ok)return setStatus(p.detail||'Unable to create Copilot session.');copilotState.sessionId=p.id;if(clear){document.querySelector('#copilotConversation').innerHTML='<div class="copilot-empty"><span class="copilot-spark">\u2726</span><h2>New Copilot session</h2><p>Ask a question grounded in the selected dataset and audit evidence.</p></div>';document.querySelector('#copilotFollowups').classList.add('hidden')}await loadCopilotContext()}
async function loadCopilotSession(id){const r=await fetch(`/copilot/sessions/${id}`),p=await r.json().catch(()=>({}));if(!r.ok)return setStatus(p.detail||'Unable to load session.');copilotState.sessionId=id;const s=p.session||{};document.querySelector('#copilotDataset').value=s.dataset_id||'';await loadCopilotContext();document.querySelector('#copilotAudit').value=s.audit_id||'';document.querySelector('#copilotCompare').value=s.compare_audit_id||'';document.querySelector('#copilotMode').value=s.analysis_mode||'general';const root=document.querySelector('#copilotConversation');root.innerHTML=(p.messages||[]).map(m=>m.role==='user'?renderCopilotUser(m.content,m.created_at):renderCopilotAnswer(m.evidence,m.created_at)).join('')||'<div class="copilot-empty"><h2>Empty session</h2><p>Ask your first question.</p></div>';document.querySelector('#copilotFollowups').classList.toggle('hidden',!(p.messages||[]).length)}
function renderCopilotUser(text,date=new Date()){return `<article class="copilot-message user"><span class="copilot-avatar">PK</span><div><p>${copilotEscape(text)}</p><time>${copilotDate(date)}</time></div></article>`}
function renderCopilotAnswer(data,date=new Date()){const r=data?.answer?data:{answer:data?.content||'Analysis completed.',summary:{},factors:[],actions:[],evidence:{}};if(r.response_type==='conversation')return `<article class="copilot-message assistant conversational"><span class="copilot-avatar ai">\u2726</span><div class="copilot-answer copilot-conversational-answer"><p class="copilot-answer-lead">${copilotEscape(r.answer)}</p><time>${copilotDate(date)}</time></div></article>`;if(r.response_type==='empty_context')return `<article class="copilot-message assistant"><span class="copilot-avatar ai">\u2726</span><div class="copilot-answer copilot-context-required"><p class="copilot-answer-lead">${copilotEscape(r.answer)}</p><ul class="copilot-actions-list">${(r.actions||[]).map(x=>`<li>\u2192 ${copilotEscape(x)}</li>`).join('')}</ul><time>${copilotDate(date)}</time></div></article>`;return `<article class="copilot-message assistant"><span class="copilot-avatar ai">\u2726</span><div class="copilot-answer"><p class="copilot-answer-lead">${copilotEscape(r.answer)}</p><h3>Summary of changes</h3><div class="copilot-summary-grid"><article><strong>${r.summary?.critical??0}</strong><span>Critical issues</span></article><article><strong>${r.summary?.high??0}</strong><span>High issues</span></article><article><strong>${r.summary?.passed_rules??0}</strong><span>Passed rules</span></article></div><h3>Top contributing factors</h3><ol>${(r.factors||[]).map(x=>`<li><strong>${copilotEscape(x.title)}</strong><span>${x.affected_rows||0} affected rows${x.columns?.length?` \u00b7 ${copilotEscape(x.columns.join(', '))}`:''}</span></li>`).join('')||'<li>No material contributing factors were found.</li>'}</ol><h3>Recommended actions</h3><ul class="copilot-actions-list">${(r.actions||[]).map(x=>`<li>\u2192 ${copilotEscape(x)}</li>`).join('')}</ul><details class="copilot-evidence-details"><summary>Evidence</summary><div><button type="button" data-copilot-open="rules">${r.evidence?.failed_rules||0} Failed Rules</button><button type="button" data-copilot-open="drift">${r.evidence?.drift_events||0} Schema Drift Events</button><button type="button" data-copilot-open="contracts">${r.evidence?.contract_violations||0} Contract Issues</button><button type="button" data-copilot-open="audit">Audit Run Details</button></div></details><time>${copilotDate(date)}</time></div></article>`}
async function askCopilot(question){if(!copilotState.sessionId)await createCopilotSession(false);const root=document.querySelector('#copilotConversation');if(root.querySelector('.copilot-empty'))root.innerHTML='';root.insertAdjacentHTML('beforeend',renderCopilotUser(question));root.insertAdjacentHTML('beforeend','<article id="copilotThinking" class="copilot-message assistant"><span class="copilot-avatar ai">\u2726</span><div class="copilot-thinking">Analyzing governed evidence\u2026</div></article>');root.scrollTop=root.scrollHeight;const body={question,dataset_id:Number(document.querySelector('#copilotDataset').value)||null,audit_id:document.querySelector('#copilotAudit').value||null,compare_audit_id:document.querySelector('#copilotCompare').value||null,analysis_mode:document.querySelector('#copilotMode').value};const r=await fetch(`/copilot/sessions/${copilotState.sessionId}/ask`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),p=await r.json().catch(()=>({}));document.querySelector('#copilotThinking')?.remove();if(!r.ok){setStatus(p.detail||'Copilot analysis failed.');return}copilotState.currentResponse=p.response;root.insertAdjacentHTML('beforeend',renderCopilotAnswer(p.response));renderCopilotEvidence(p.context||{});document.querySelector('#copilotFollowups').classList.remove('hidden');root.scrollTop=root.scrollHeight;await loadCopilotContext()}
function copilotNavigate(route){navigateToPage(route)}
function bindCopilot(){document.querySelector('#copilotAskForm')?.addEventListener('submit',e=>{e.preventDefault();const q=document.querySelector('#copilotQuestion').value.trim();if(!q)return;document.querySelector('#copilotQuestion').value='';askCopilot(q)});document.querySelector('#copilotNewSession')?.addEventListener('click',()=>createCopilotSession(true));['copilotDataset','copilotAudit','copilotCompare'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('change',loadCopilotContext));document.querySelector('#copilotMode')?.addEventListener('change',()=>{});document.querySelector('#copilotFollowups')?.addEventListener('click',e=>{const b=e.target.closest('[data-copilot-question]');if(b)askCopilot(b.dataset.copilotQuestion)});document.querySelector('#copilotConversation')?.addEventListener('click',e=>{const b=e.target.closest('[data-copilot-open]');if(!b)return;const map={rules:'rules',contracts:'rules',drift:'drift',audit:'audit'};copilotNavigate(map[b.dataset.copilotOpen]||'overview')});document.querySelector('#copilotOpenAudit')?.addEventListener('click',()=>copilotNavigate('audit'));document.querySelector('#copilotOpenDataset')?.addEventListener('click',()=>copilotNavigate('datasets'));document.querySelector('#copilotCompareAudits')?.addEventListener('click',()=>copilotNavigate('versions'));document.querySelector('#copilotCreateRule')?.addEventListener('click',()=>{copilotNavigate('rules');setTimeout(()=>document.querySelector('#newRuleButton')?.click(),300)});document.querySelector('#copilotOpenRemediation')?.addEventListener('click',()=>copilotNavigate('remediation'));document.querySelector('#copilotCreateAction')?.addEventListener('click',createCopilotActionPoint);document.querySelector('#copilotGuardrails')?.addEventListener('click',()=>showAppMessage({eyebrow:'AI governance',title:'Reliability Copilot guardrails',description:'Copilot is read-only by default. Dataset changes, rule publication, and remediation require explicit human review and approval. Sensitive values are masked from generated explanations.',confirmLabel:'Understood',hideCancel:true}));document.querySelector('#closeDeleteCopilotSessionDialog')?.addEventListener('click',()=>document.querySelector('#deleteCopilotSessionDialog').close());document.querySelector('#cancelDeleteCopilotSession')?.addEventListener('click',()=>document.querySelector('#deleteCopilotSessionDialog').close());document.querySelector('#confirmDeleteCopilotSession')?.addEventListener('click',confirmDeleteCopilotSession)}
function openDeleteCopilotSession(id,title){copilotState.deleteSessionId=id;setText('#deleteCopilotSessionDescription',`Delete \u201c${title||'this session'}\u201d? The conversation and its messages will be removed. Existing Action Points will remain available.`);document.querySelector('#deleteCopilotSessionDialog')?.showModal()}
async function confirmDeleteCopilotSession(){const id=copilotState.deleteSessionId;if(!id)return;const response=await fetch(`/copilot/sessions/${id}`,{method:'DELETE'}),payload=await response.json().catch(()=>({}));if(!response.ok){setStatus(payload.detail||'Unable to delete Copilot session.');return}document.querySelector('#deleteCopilotSessionDialog')?.close();copilotState.deleteSessionId=null;if(copilotState.sessionId===id){copilotState.sessionId=null;copilotState.currentResponse=null;document.querySelector('#copilotConversation').innerHTML='<div class="copilot-empty"><span class="copilot-spark">\u2726</span><h2>Start a new analysis</h2><p>Select a dataset and audit, then ask a question grounded in workspace evidence.</p></div>';document.querySelector('#copilotFollowups').classList.add('hidden')}setStatus('Copilot session deleted.');await loadCopilotContext()}
async function createCopilotActionPoint(){const r=copilotState.currentResponse;if(!r)return setStatus('Ask Copilot a question before creating an Action Point.');const description=(r.actions||[]).join('\n');const body={title:(r.answer||'Reliability follow-up').slice(0,120),description:description||r.answer,priority:(r.summary?.critical||0)>0?'high':'medium',dataset_id:Number(document.querySelector('#copilotDataset').value)||null,audit_id:document.querySelector('#copilotAudit').value||null,session_id:copilotState.sessionId};const res=await fetch('/copilot/action-points',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),p=await res.json().catch(()=>({}));setStatus(res.ok?`Action Point #${p.id} created.`:(p.detail||'Unable to create Action Point.'))}
bindCopilot();

// Feature 24: Reports & Executive Reporting
const reportState={payload:null,charts:{}};
function reportQuery(){const q=new URLSearchParams();const d=document.querySelector('#reportDataset')?.value;if(d)q.set('dataset_id',d);const f=document.querySelector('#reportDateFrom')?.value,t=document.querySelector('#reportDateTo')?.value;if(f)q.set('date_from',`${f}T00:00:00Z`);if(t)q.set('date_to',`${t}T23:59:59Z`);q.set('report_type',document.querySelector('#reportType')?.value||'executive');return q.toString()}
async function openReportsPage(){authEls.profileMenu?.classList.add('hidden');hideAllPages();animatePage(document.querySelector('#reportsPage'));document.querySelector('#reportsNavButton')?.classList.add('active');setText('#topbarPageTitle','Reports');setText('#topbarBreadcrumb','Home / Governance / Reports');await loadReports()}
async function loadReports(){const r=await fetch(`/reports?${reportQuery()}`),p=await r.json().catch(()=>({}));if(!r.ok){setStatus(p.detail||'Unable to load reports.');return}reportState.payload=p;renderReports()}
function reportChart(id,type,data,options={}){if(typeof Chart==='undefined')return;reportState.charts[id]?.destroy();const el=document.querySelector(`#${id}`);if(!el)return;reportState.charts[id]=new Chart(el,{type,data,options:{responsive:true,maintainAspectRatio:false,...options}})}
function renderReports(){const p=reportState.payload||{},m=p.metrics||{},c=p.charts||{};setText('#reportScore',m.score==null?'\u2014':`${m.score}/100`);setText('#reportDatasets',m.datasets||0);setText('#reportIssues',m.active_issues||0);setText('#reportFailedRules',m.failed_rules||0);setText('#reportDrift',m.drift_events||0);const ds=document.querySelector('#reportDataset'),cur=ds.value;ds.innerHTML='<option value="">All datasets</option>'+(p.datasets||[]).map(x=>`<option value="${x.id}">${escapeHtml(x.name)}</option>`).join('');ds.value=cur;
reportChart('reportReliabilityChart','line',{labels:(c.reliability||[]).map(x=>x.label),datasets:[{label:'Reliability score',data:(c.reliability||[]).map(x=>x.score),tension:.35,fill:false}]},{plugins:{legend:{display:false}},scales:{y:{min:0,max:100}}});
reportChart('reportSeverityChart','doughnut',{labels:(c.severity||[]).map(x=>x.label),datasets:[{data:(c.severity||[]).map(x=>x.count)}]},{cutout:'66%',plugins:{legend:{position:'bottom'}}});
reportChart('reportDatasetRankingChart','bar',{labels:(c.dataset_ranking||[]).map(x=>x.dataset),datasets:[{label:'Score',data:(c.dataset_ranking||[]).map(x=>x.score)}]},{indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{min:0,max:100}}});
reportChart('reportRulePassChart','line',{labels:(c.rule_pass_rate||[]).map(x=>x.label),datasets:[{label:'Pass rate',data:(c.rule_pass_rate||[]).map(x=>x.rate),tension:.35}]},{plugins:{legend:{display:false}},scales:{y:{min:0,max:100}}});
reportChart('reportCategoryChart','bar',{labels:(c.categories||[]).map(x=>x.label),datasets:[{label:'Issues',data:(c.categories||[]).map(x=>x.count)}]},{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}});
const rem=c.remediation_impact||[];reportChart('reportRemediationChart','bar',{labels:rem.map(x=>x.dataset),datasets:[{label:'Before',data:rem.map(x=>x.before)},{label:'After',data:rem.map(x=>x.after)}]},{scales:{y:{min:0,max:100}}});
reportChart('reportColumnsChart','bar',{labels:(c.affected_columns||[]).map(x=>x.column),datasets:[{label:'Issues',data:(c.affected_columns||[]).map(x=>x.count)}]},{indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{beginAtZero:true}}});
reportChart('reportScatterChart','scatter',{datasets:[{label:'Datasets',data:(c.score_issue_scatter||[]).map(x=>({x:x.issues,y:x.score,dataset:x.dataset}))}]},{plugins:{tooltip:{callbacks:{label:x=>`${x.raw.dataset}: ${x.raw.y}/100, ${x.raw.x} issues`}}},scales:{x:{title:{display:true,text:'Active issues'},beginAtZero:true},y:{title:{display:true,text:'Reliability score'},min:0,max:100}}});
const rows=document.querySelector('#reportRows'),reports=p.reports||[];rows.innerHTML=reports.length?reports.map(r=>`<div class="report-row"><span><strong>${escapeHtml(r.name)}</strong><small>${escapeHtml(titleCase(r.report_type))}</small></span><span>${escapeHtml(titleCase(r.report_type))}</span><span>${escapeHtml(r.format.toUpperCase())}</span><span>${new Date(r.generated_at).toLocaleString()}</span><span><button class="secondary-button" data-report-download="${r.format}">Download</button></span></div>`).join(''):'<div class="empty-row">No generated reports yet.</div>';setText('#reportCount',`${reports.length} reports`);rows.querySelectorAll('[data-report-download]').forEach(b=>b.onclick=()=>exportReport(b.dataset.reportDownload));const schedules=document.querySelector('#reportSchedules');schedules.innerHTML=(p.schedules||[]).length?(p.schedules||[]).map(x=>`<article><div><strong>${escapeHtml(x.name)}</strong><small>${escapeHtml(titleCase(x.report_type))} \u00b7 ${escapeHtml(titleCase(x.frequency))} \u00b7 ${x.format.toUpperCase()}</small></div><button class="icon-button" data-delete-report-schedule="${x.id}" title="Delete schedule">\u00d7</button></article>`).join(''):'<div class="empty-row">No saved report schedules.</div>';schedules.querySelectorAll('[data-delete-report-schedule]').forEach(b=>b.onclick=()=>deleteReportSchedule(Number(b.dataset.deleteReportSchedule)))}
function currentReportFilters(){return {dataset_id:document.querySelector('#reportDataset')?.value||null,date_from:document.querySelector('#reportDateFrom')?.value||null,date_to:document.querySelector('#reportDateTo')?.value||null}}
function openReportDialog(){document.querySelector('#reportName').value=`${document.querySelector('#reportType').selectedOptions[0].text} Report`;document.querySelector('#reportDialog').showModal()}
async function saveReport(e){e.preventDefault();const body={name:document.querySelector('#reportName').value,report_type:document.querySelector('#reportType').value,format:document.querySelector('#reportFormat').value,filters:currentReportFilters()};const r=await fetch('/reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),p=await r.json().catch(()=>({}));if(!r.ok)return setStatus(p.detail||'Unable to generate report.');document.querySelector('#reportDialog').close();setStatus('Report generated.');await loadReports();exportReport(body.format)}
function openReportScheduleDialog(){document.querySelector('#reportScheduleName').value=`Weekly ${document.querySelector('#reportType').selectedOptions[0].text}`;document.querySelector('#reportScheduleDialog').showModal()}
async function saveReportSchedule(e){e.preventDefault();const body={name:document.querySelector('#reportScheduleName').value,report_type:document.querySelector('#reportType').value,frequency:document.querySelector('#reportFrequency').value,format:document.querySelector('#reportScheduleFormat').value,filters:currentReportFilters()};const r=await fetch('/reports/schedules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),p=await r.json().catch(()=>({}));if(!r.ok)return setStatus(p.detail||'Unable to schedule report.');document.querySelector('#reportScheduleDialog').close();setStatus('Report schedule saved.');await loadReports()}
function exportReport(format){window.location.href=`/reports/export/${format}`}
async function deleteReportSchedule(id){const r=await fetch(`/reports/schedules/${id}`,{method:'DELETE'});if(!r.ok)return setStatus('Unable to delete report schedule.');setStatus('Report schedule deleted.');await loadReports()}
function resetReportFilters(){document.querySelector('#reportType').value='executive';document.querySelector('#reportDataset').value='';document.querySelector('#reportDateFrom').value='';document.querySelector('#reportDateTo').value='';loadReports()}
['reportType','reportDataset','reportDateFrom','reportDateTo'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('change',loadReports));document.querySelector('#resetReportFilters')?.addEventListener('click',resetReportFilters);['newReportButton','quickNewReport'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('click',openReportDialog));['scheduleReportButton','quickScheduleReport'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('click',openReportScheduleDialog));['reportExportPdf','quickPdf'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('click',()=>exportReport('pdf')));['reportExportCsv','quickCsv'].forEach(id=>document.querySelector(`#${id}`)?.addEventListener('click',()=>exportReport('csv')));document.querySelector('#reportForm')?.addEventListener('submit',saveReport);document.querySelector('#reportScheduleForm')?.addEventListener('submit',saveReportSchedule);document.querySelector('#closeReportDialog')?.addEventListener('click',()=>document.querySelector('#reportDialog').close());document.querySelector('#cancelReportDialog')?.addEventListener('click',()=>document.querySelector('#reportDialog').close());document.querySelector('#closeReportScheduleDialog')?.addEventListener('click',()=>document.querySelector('#reportScheduleDialog').close());document.querySelector('#cancelReportScheduleDialog')?.addEventListener('click',()=>document.querySelector('#reportScheduleDialog').close());


// Final UI consistency utilities
let appMessageResolver = null;
function showAppMessage({eyebrow='Notice',title='Information',description='',confirmLabel='Close',cancelLabel='Cancel',danger=false,hideCancel=false}={}){
  const dialog=document.querySelector('#appMessageDialog');
  if(!dialog)return Promise.resolve(false);
  setText('#appMessageEyebrow',eyebrow);setText('#appMessageTitle',title);setText('#appMessageDescription',description);
  const confirmButton=document.querySelector('#confirmAppMessageDialog'),cancelButton=document.querySelector('#cancelAppMessageDialog');
  confirmButton.textContent=confirmLabel;cancelButton.textContent=cancelLabel;cancelButton.classList.toggle('hidden',hideCancel);
  confirmButton.classList.toggle('danger-button',danger);
  if(dialog.open)dialog.close();dialog.showModal();
  return new Promise(resolve=>{appMessageResolver=resolve;setTimeout(()=>confirmButton.focus(),0)});
}
function confirmAppAction(options={}){return showAppMessage({...options,hideCancel:false})}
function settleAppMessage(result){const dialog=document.querySelector('#appMessageDialog');if(dialog?.open)dialog.close();const resolve=appMessageResolver;appMessageResolver=null;if(resolve)resolve(result)}
function bindAppMessageDialog(){
  document.querySelector('#confirmAppMessageDialog')?.addEventListener('click',()=>settleAppMessage(true));
  document.querySelector('#cancelAppMessageDialog')?.addEventListener('click',()=>settleAppMessage(false));
  document.querySelector('#closeAppMessageDialog')?.addEventListener('click',()=>settleAppMessage(false));
  document.querySelector('#appMessageDialog')?.addEventListener('cancel',event=>{event.preventDefault();settleAppMessage(false)});
}
const shellSvgIcons={
  overview:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11 12 4l8 7v9H4z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M9 20v-6h6v6" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>',
  datasets:'<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5" rx="7" ry="3" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M5 5v14c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>',
  versions:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h10M7 12h10M7 17h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><path d="m4 7 1-1v2m-1 4 1-1v2m-1 4 1-1v2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  audit:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>',
  drift:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 14 4-4 4 4 4-6 4 3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  schedules:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 9v4l3 2M8 3v3m8-3v3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  alerts:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16h12l-1.5-2.5V10a4.5 4.5 0 0 0-9 0v3.5L6 16Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M10 19h4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  rules:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5zM8 9h8M8 13h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  remediation:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 5 5 5-9 9H5v-5l9-9Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m12 7 5 5" stroke="currentColor" stroke-width="1.7"/></svg>',
  team:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3 19c.5-4 2.5-6 6-6s5.5 2 6 6M16 8h5m-2.5-2.5v5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
};
function applyConsistentShellIcons(){
 const map={overviewNavButton:'overview',datasetsNavButton:'datasets',versionsNavButton:'versions',auditNavButton:'audit',driftNavButton:'drift',schedulesNavButton:'schedules',alertsNavButton:'alerts',rulesNavButton:'rules',remediationNavButton:'remediation',teamNavButton:'team'};
 Object.entries(map).forEach(([id,key])=>{const icon=document.querySelector(`#${id} .nav-icon`);if(icon){icon.classList.add('svg-nav-icon');icon.innerHTML=shellSvgIcons[key]}});
 const notification=document.querySelector('.notification-button');if(notification){notification.childNodes[0].textContent='';notification.insertAdjacentHTML('afterbegin',shellSvgIcons.alerts)}
}
function enhanceKeyboardAccessibility(){
 window.DRC?.dom?.initialiseAccessibility();
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',()=>{bindAppMessageDialog();applyConsistentShellIcons();enhanceKeyboardAccessibility()})}else{bindAppMessageDialog();applyConsistentShellIcons();enhanceKeyboardAccessibility()}
