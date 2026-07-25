(function () {
  "use strict";
  function setBusy(element, busy, label = "Working") {
    if (!element) return;
    element.toggleAttribute("aria-busy", Boolean(busy));
    if (busy) element.setAttribute("aria-label", label);
    else element.removeAttribute("aria-label");
  }
  function setStatus(message, { assertive = false } = {}) {
    window.DRC?.dom?.announce(message, assertive ? "assertive" : "polite");
  }
  window.DRC = window.DRC || {};
  window.DRC.feedback = Object.freeze({ setBusy, setStatus });
})();
