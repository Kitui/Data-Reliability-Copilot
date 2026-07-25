(function () {
  "use strict";
  const FOCUSABLE = [
    "a[href]", "button:not([disabled])", "input:not([disabled])", "select:not([disabled])",
    "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])"
  ].join(",");

  function announce(message, priority = "polite") {
    const region = document.querySelector(priority === "assertive" ? "#appAlertRegion" : "#appStatusRegion");
    if (!region) return;
    region.textContent = "";
    window.requestAnimationFrame(() => { region.textContent = String(message || ""); });
  }

  function trapDialogFocus(dialog) {
    if (!dialog || dialog.dataset.focusTrapBound === "true") return;
    dialog.dataset.focusTrapBound = "true";
    dialog.addEventListener("keydown", (event) => {
      if (event.key !== "Tab" || !dialog.open) return;
      const items = [...dialog.querySelectorAll(FOCUSABLE)].filter((node) => node.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
  }

  function initialiseAccessibility() {
    document.querySelectorAll("dialog").forEach(trapDialogFocus);
    document.querySelectorAll("button:not([type])").forEach((button) => button.setAttribute("type", "button"));
    document.querySelectorAll("[data-dataset-id],[data-connector-id],[data-alert-id]").forEach((row) => {
      if (!row.hasAttribute("tabindex")) row.tabIndex = 0;
      if (!row.hasAttribute("role")) row.setAttribute("role", "button");
      if (row.dataset.keyboardBound !== "true") {
        row.dataset.keyboardBound = "true";
        row.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            row.click();
          }
        });
      }
    });
    document.querySelectorAll(".icon-button:not([aria-label])").forEach((button) => {
      const label = button.getAttribute("title") || button.textContent.trim() || "Action";
      button.setAttribute("aria-label", label);
    });
  }

  window.DRC = window.DRC || {};
  window.DRC.dom = Object.freeze({ announce, trapDialogFocus, initialiseAccessibility });
})();
