(function () {
  "use strict";
  const DISPLAY_TIME_ZONE = "Africa/Nairobi";

  function parseServerDate(value) {
    if (!value) return null;
    if (value instanceof Date) return value;
    const raw = String(value).trim();
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
    const parsed = new Date(hasZone ? raw : `${raw}Z`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function formatDateTime(value, options = {}) {
    const parsed = parseServerDate(value);
    if (!parsed) return "--";
    return new Intl.DateTimeFormat("en-KE", {
      timeZone: DISPLAY_TIME_ZONE,
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: options.includeSeconds === false ? undefined : "2-digit",
      hour12: true,
      ...options,
    }).format(parsed);
  }

  window.DRC = window.DRC || {};
  window.DRC.datetime = Object.freeze({ DISPLAY_TIME_ZONE, parseServerDate, formatDateTime });
})();
