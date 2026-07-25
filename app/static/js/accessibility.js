(function () {
  "use strict";
  function boot() { window.DRC?.dom?.initialiseAccessibility(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
