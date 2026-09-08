// US-21 (Architecture.md 6.19, S21-2): shared nav-bar version display, used
// by all 4 static pages (index/glossary/history/settings.html) so the
// fetch-and-render logic exists in exactly one place instead of being
// copy-pasted per page.
//
// Fetches GET /api/version once per page load and fills <span
// id="app-version">. Network error or a missing/"unknown" version leaves the
// span blank silently (S21-2) — never throws, so a slow/broken API can never
// block the rest of the page from rendering.
(function () {
  function render(text) {
    const el = document.getElementById("app-version");
    if (el) {
      el.textContent = text;
    }
  }

  fetch("/api/version")
    .then((res) => (res.ok ? res.json() : null))
    .then((body) => {
      const version = body && body.version;
      if (version && version !== "unknown") {
        render(`v${version}`);
      }
    })
    .catch(() => {
      // non-fatal — nav bar just shows no version.
    });
})();
