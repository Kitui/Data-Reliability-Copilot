(function () {
  "use strict";
  const nativeFetch = window.fetch.bind(window);
  const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

  function readCookie(name) {
    return document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(`${name}=`))
      ?.split("=")
      .slice(1)
      .join("=") || "";
  }

  function secureFetch(input, init = {}) {
    const method = String(init.method || "GET").toUpperCase();
    const headers = new Headers(init.headers || {});
    if (!SAFE_METHODS.has(method)) {
      const csrf = decodeURIComponent(readCookie("drc_csrf"));
      if (csrf) headers.set("X-CSRF-Token", csrf);
    }
    return nativeFetch(input, {
      ...init,
      headers,
      credentials: init.credentials || "same-origin",
    });
  }

  window.DRC = window.DRC || {};
  window.DRC.http = Object.freeze({ readCookie, secureFetch });
  window.fetch = secureFetch;
})();
