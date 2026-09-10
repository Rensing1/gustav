/* Keep appearance independent of authentication state and usable from mail links. */
(function () {
  function validTheme(value) {
    return value === "light" || value === "dark" ? value : null;
  }
  var url = new URL(window.location.href);
  var hint = validTheme(url.searchParams.get("gustav_theme"));
  var saved = null;
  try { saved = validTheme(localStorage.getItem("gustav-theme")); } catch (_) { /* Storage may be unavailable. */ }
  var theme = hint || saved || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
  if (hint) {
    try { localStorage.setItem("gustav-theme", theme); } catch (_) { /* Keep the in-page selection. */ }
  }
  // Consume only our display hint; preserve all OIDC parameters and history state.
  if (url.searchParams.has("gustav_theme")) {
    url.searchParams.delete("gustav_theme");
    history.replaceState(history.state, "", url.toString());
  }
  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("kc-theme-toggle");
    if (!button) return;
    function updateButton() {
      var label = theme === "dark" ? "Helle Darstellung" : "Dunkle Darstellung";
      button.textContent = label;
      button.setAttribute("aria-label", label + " aktivieren");
    }
    updateButton();
    button.addEventListener("click", function () {
      theme = theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", theme);
      try { localStorage.setItem("gustav-theme", theme); } catch (_) { /* Keep the in-page selection. */ }
      updateButton();
    });
  });
})();
