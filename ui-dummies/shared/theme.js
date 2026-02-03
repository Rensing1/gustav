const THEMES = ["rose-pine-dawn", "everforest-dark-hard"];

function getPreferredTheme() {
  const saved = localStorage.getItem("gustav-theme");
  if (saved && THEMES.includes(saved)) return saved;
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "everforest-dark-hard" : "rose-pine-dawn";
}

export function setTheme(theme) {
  if (!THEMES.includes(theme)) return;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("gustav-theme", theme);
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || getPreferredTheme();
  const idx = THEMES.indexOf(current);
  const next = THEMES[(idx + 1) % THEMES.length];
  setTheme(next);
}

function wireToggleButtons() {
  const buttons = document.querySelectorAll("[data-theme-toggle]");
  buttons.forEach((btn) => {
    if (btn.__themeWired) return;
    btn.__themeWired = true;
    btn.addEventListener("click", () => toggleTheme());
  });
}

function initTheme() {
  setTheme(getPreferredTheme());
  wireToggleButtons();

  // Follow system changes only when the user has not pinned a theme.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
    if (localStorage.getItem("gustav-theme")) return;
    setTheme(e.matches ? "everforest-dark-hard" : "rose-pine-dawn");
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initTheme);
} else {
  initTheme();
}

