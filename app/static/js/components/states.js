(function () {
  "use strict";
  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    })[character]);
  }
  function empty({ title = "Nothing here yet", message = "No records are available.", action = "" } = {}) {
    return `<div class="shared-state shared-empty-state" role="status"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p>${action}</div>`;
  }
  function error({ title = "Unable to load", message = "Please try again." } = {}) {
    return `<div class="shared-state shared-error-state" role="alert"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p></div>`;
  }
  function loading({ label = "Loading" } = {}) {
    return `<div class="shared-state shared-loading-state" role="status" aria-live="polite"><span class="ui-spinner" aria-hidden="true"></span><span>${escapeHtml(label)}</span></div>`;
  }
  window.DRC = window.DRC || {};
  window.DRC.states = Object.freeze({ empty, error, loading });
})();
