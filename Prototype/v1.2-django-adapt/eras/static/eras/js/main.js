(function () {
  function getCookie(name) {
    const cookie = document.cookie.split(";").map(v => v.trim()).find(v => v.startsWith(name + "="));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  }

  async function apiFetch(url, options) {
    const config = Object.assign({ credentials: "same-origin" }, options || {});
    config.headers = Object.assign({ Accept: "application/json" }, config.headers || {});
    const method = String(config.method || "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
      config.headers["X-CSRFToken"] = getCookie("csrftoken");
      // FormData must keep the browser-generated multipart boundary. JSON
      // requests continue to receive the existing application/json header.
      const isFormData = typeof FormData !== "undefined" && config.body instanceof FormData;
      if (config.body && !isFormData && !config.headers["Content-Type"]) config.headers["Content-Type"] = "application/json";
    }
    const response = await fetch(url, config);
    let payload = {};
    try { payload = await response.json(); } catch (_) { payload = {}; }
    if (!response.ok) {
      const error = new Error(payload?.error?.message || `API-Fehler (${response.status})`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function caseNumberFromStorageKey(key) {
    const prefix = "bene-eras-case:";
    return String(key || "").startsWith(prefix) ? String(key).slice(prefix.length) : null;
  }

  window.erasApi = { fetch: apiFetch };

  // Compatibility layer: the checklist UI keeps its existing storage calls,
  // while every real checklist is persisted through Django and a treatment case.
  window.storage = {
    async get(key) {
      const caseNumber = caseNumberFromStorageKey(key);
      if (caseNumber) {
        const payload = await apiFetch(`/api/cases/${encodeURIComponent(caseNumber)}/state/`);
        window.erasBackend = payload;
        return { value: JSON.stringify(payload.state), summary: payload.summary, derived: payload.derived, revision: payload.revision };
      }
      throw new Error("Checklisten können nur fallbezogen gespeichert werden.");
    },
    async set(key, value, options) {
      const caseNumber = caseNumberFromStorageKey(key);
      if (caseNumber) {
        const state = typeof value === "string" ? JSON.parse(value) : value;
        const body = { state };
        // With baseRevision the backend answers 409 if another workstation
        // saved in the meantime, instead of silently overwriting its changes.
        if (options && Number.isInteger(options.baseRevision)) body.baseRevision = options.baseRevision;
        const payload = await apiFetch(`/api/cases/${encodeURIComponent(caseNumber)}/state/`, {
          method: "PUT",
          body: JSON.stringify(body)
        });
        window.erasBackend = payload;
        return { value: JSON.stringify(payload.state), summary: payload.summary, derived: payload.derived, revision: payload.revision };
      }
      throw new Error("Checklisten können nur fallbezogen gespeichert werden.");
    },
    async delete(key) {
      const caseNumber = caseNumberFromStorageKey(key);
      if (caseNumber) {
        await apiFetch(`/api/cases/${encodeURIComponent(caseNumber)}/state/`, { method: "DELETE" });
        return null;
      }
      throw new Error("Checklisten können nur fallbezogen gespeichert werden.");
    }
  };
})();
