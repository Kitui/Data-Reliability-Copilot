const state = {
  audit: null,
  history: [],
  remediation: null,
  contract: null,
  selectedIssueId: null,
  selectedColumn: null,
  selectedIssueIds: new Set(),
  selectedActionIds: new Set(),
  filters: { category: "all", severity: "all", status: "all", search: "" },
  chat: [],
  busy: false,
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
};

bindEvents();
loadHistory();
renderPromptChips();

function bindEvents() {
  els.uploadButton.addEventListener("click", uploadCsv);
  els.sampleButton.addEventListener("click", () => runAudit("/audits/sample", { method: "POST" }));
  els.emptySampleButton.addEventListener("click", () => runAudit("/audits/sample", { method: "POST" }));
  els.emptyRulesButton.addEventListener("click", () => activateTab("rules"));
  els.refreshHistoryButton.addEventListener("click", loadHistory);
  els.regenerateButton.addEventListener("click", regenerateSummary);
  els.loadRemediationButton.addEventListener("click", loadRemediation);
  els.loadContractButton.addEventListener("click", loadContract);
  els.useContractButton.addEventListener("click", useContractAsRules);
  els.copyScriptButton.addEventListener("click", copySelectedScript);
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
  syncRulesFromBuilder(false);
  const form = new FormData();
  form.append("file", els.fileInput.files[0]);
  if (els.rulesInput.value.trim()) form.append("rules_json", els.rulesInput.value.trim());
  await runAudit("/audits/upload", { method: "POST", body: form });
}

async function runAudit(url, options) {
  setBusy(true);
  setStatus("Auditing...");
  try {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Audit failed.");
    renderAudit(payload);
    try {
      await loadHistory();
    } catch (historyError) {
      console.warn(historyError);
      setStatus(`Completed audit for ${payload.dataset_name}. History refresh failed.`);
      return;
    }
    setStatus(`Completed audit for ${payload.dataset_name}`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    setBusy(false);
  }
}

async function loadHistory() {
  const response = await fetch("/audits");
  state.history = await response.json();
  renderHistory();
  renderCompareOptions();
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
  renderAudit(await response.json());
  setStatus("Saved audit loaded.");
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
  renderBreakdown(audit.score);
  renderFilters(audit.issues);
  renderIssues();
  renderColumns();
  renderInspector();
  renderCompareOptions();
  renderContractMini();
  renderChat();
  renderHistory();
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
    const card = document.createElement("article");
    card.className = `column-card ${state.selectedColumn === column.name ? "selected" : ""}`;
    card.innerHTML = `
      <button class="column-main" data-open-column="${escapeHtml(column.name)}">
        <strong>${escapeHtml(column.name)}</strong>
        <span>${escapeHtml(column.inferred_type)} - ${related.length} signals</span>
      </button>
      <label>Missing <div class="bar"><i style="width:${Math.round(column.missing_rate * 100)}%"></i></div></label>
      <label>Unique <div class="bar"><i style="width:${Math.round(column.unique_rate * 100)}%"></i></div></label>
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
  actions.innerHTML = state.remediation.actions.map((action) => `
    <article class="action">
      <label class="check-row"><input type="checkbox" data-select-action="${escapeHtml(action.issue_id)}" ${state.selectedActionIds.has(action.issue_id) ? "checked" : ""}> <strong>${escapeHtml(action.title)}</strong></label>
      <p>${escapeHtml(action.description)}</p>
      <div class="code-head"><span>${escapeHtml(action.action_type)} - ${escapeHtml(action.risk)} risk</span><button data-copy-code="${escapeHtml(action.issue_id)}">Copy</button></div>
      <pre>${escapeHtml(action.pandas_code)}</pre>
    </article>
  `).join("");
  document.querySelectorAll("[data-select-action]").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) state.selectedActionIds.add(box.dataset.selectAction);
      else state.selectedActionIds.delete(box.dataset.selectAction);
      renderSelectedScript();
    });
  });
  document.querySelectorAll("[data-copy-code]").forEach((button) => {
    button.addEventListener("click", () => copyActionCode(button.dataset.copyCode));
  });
  renderSelectedScript();
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
  const question = questionOverride || els.analystQuestion.value.trim();
  if (!state.audit || !question) return;
  state.chat.push({ role: "user", text: question });
  renderChat();
  const response = await fetch(`/audits/${state.audit.audit_id}/analyst`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const payload = await response.json();
  state.chat.push({ role: "assistant", text: payload.answer, source: payload.source, issueIds: payload.supporting_issue_ids });
  els.analystQuestion.value = "";
  renderChat();
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
    "Generate a manager summary",
    "Which fields are risky for ML?",
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
  return ["open", "in_progress", "fixed", "ignored", "accepted_risk"].map((status) => `<option value="${status}" ${status === current ? "selected" : ""}>${status}</option>`).join("");
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
  els.statusText.textContent = message;
}

function setBusy(isBusy) {
  state.busy = isBusy;
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
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
