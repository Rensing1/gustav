const FALLBACK_DEFAULT_APP_PATH =
  "/learning/courses/11111111-1111-1111-1111-111111111111/units/22222222-2222-2222-2222-222222222222";

// Mirrors backend/web/components/navigation.py:ROUTE_MAP (plus a few helper routes).
const ROUTE_MAP = {
  "/": { label: "Startseite" },
  "/dashboard": { label: "Dashboard" },
  "/wissenschaft": { label: "Wissenschaft" },
  "/courses": { label: "Kurse" },
  "/courses/:course_id": { label_template: "Kurs {course_id}" },
  "/courses/:course_id/lessons": { label: "Lektionen" },
  "/courses/:course_id/lessons/:lesson_id": { label_template: "Lektion {lesson_id}" },
  "/progress": { label: "Fortschritt" },
  "/flashcards": { label: "Karteikarten" },
  "/students": { label: "Schüler" },
  "/analytics": { label: "Analytics" },
  "/content": { label: "Inhalte" },
  "/users": { label: "Nutzerverwaltung" },
  "/system": { label: "System" },
  "/settings": { label: "Einstellungen" },
  "/about": { label: "Über GUSTAV" },
  "/login": { label: "Anmelden" },

  // Student learning area
  "/learning": { label: "Meine Kurse" },
  "/learning/courses": { label: "Kurse" },
  "/learning/courses/:course_id": { label: "Kurs" },
  "/learning/courses/:course_id/units": { label: "Lerneinheiten" },
  "/learning/courses/:course_id/units/:unit_id": { label: "Lerneinheit" },

  // Teacher authoring area
  "/units": { label: "Lerneinheiten" },
  "/units/:unit_id": { label: "Lerneinheit" },
  "/units/:unit_id/edit": { label: "Bearbeiten" },
  "/units/:unit_id/sections": { label: "Abschnitte" },
  "/units/:unit_id/sections/:section_id": { label: "Abschnitt" },
};

const ROUTE_PATTERNS = Object.keys(ROUTE_MAP).sort((a, b) => b.split("/").length - a.split("/").length);

function sanitizePath(path) {
  const raw = String(path || "").split("?")[0].split("#")[0].trim();
  if (!raw) return "/";
  let normalized = raw.startsWith("/") ? raw : `/${raw}`;
  normalized = normalized.replace(/\/{2,}/g, "/");
  if (normalized.length > 1 && normalized.endsWith("/")) normalized = normalized.slice(0, -1);
  return normalized || "/";
}

function humanize(segment) {
  const cleaned = String(segment || "").replace(/[-_]/g, " ").trim();
  if (!cleaned) return "Startseite";
  if (/^\d+$/.test(cleaned)) return `ID ${cleaned}`;
  return cleaned
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.slice(0, 1).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function extractParams(pattern, path) {
  const patternSegs = String(pattern || "")
    .split("/")
    .filter(Boolean);
  const pathSegs = String(path || "")
    .split("/")
    .filter(Boolean);
  if (patternSegs.length !== pathSegs.length) return null;

  const params = {};
  for (let i = 0; i < patternSegs.length; i += 1) {
    const p = patternSegs[i];
    const s = pathSegs[i];
    if (p.startsWith(":")) {
      const key = p.slice(1);
      if (!key) return null;
      params[key] = s;
      continue;
    }
    if (p !== s) return null;
  }
  return params;
}

function matchRoute(path) {
  const current = sanitizePath(path);
  for (const pattern of ROUTE_PATTERNS) {
    const params = extractParams(pattern, current);
    if (params) return { pattern, meta: ROUTE_MAP[pattern], params };
  }
  return null;
}

function labelForPath(path) {
  const current = sanitizePath(path);
  const match = matchRoute(current);
  if (match) {
    const meta = match.meta || {};
    const template = meta.label_template;
    if (template) {
      let failed = false;
      const rendered = String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (m, key) => {
        if (Object.prototype.hasOwnProperty.call(match.params, key)) return String(match.params[key]);
        failed = true;
        return m;
      });
      if (!failed && rendered) return rendered;
    }
    if (meta.label) return String(meta.label);
  }
  if (current === "/") return "Startseite";
  const last = current.split("/").filter(Boolean).slice(-1)[0] || "";
  return humanize(last);
}

function buildCrumbs(currentPath) {
  const path = sanitizePath(currentPath);
  const crumbs = [["/", labelForPath("/")]];
  if (path === "/") return crumbs;
  const segments = path.split("/").filter(Boolean);

  let current = "";
  for (const seg of segments) {
    current = `${current}/${seg}`.replace(/\/{2,}/g, "/");
    crumbs.push([current, labelForPath(current)]);
  }
  return crumbs;
}

function getAppPathFromLocation(defaultPath) {
  const hash = String(window.location.hash || "");
  if (hash.startsWith("#/")) return sanitizePath(hash.slice(1));

  try {
    const url = new URL(window.location.href);
    const qp = url.searchParams.get("path");
    if (qp) return sanitizePath(qp);
  } catch (_) {
    // Ignore; fall back to default.
  }

  return sanitizePath(defaultPath || FALLBACK_DEFAULT_APP_PATH);
}

function setAppPath(path, { replace } = {}) {
  const next = sanitizePath(path);
  const nextHash = `#${next}`;
  if (window.location.hash === nextHash) return;
  if (replace) window.history.replaceState(null, "", nextHash);
  else window.location.hash = next;
}

function renderBreadcrumb(currentPath, { breadcrumbId, breadcrumbListId }) {
  const nav = document.getElementById(breadcrumbId);
  const list = document.getElementById(breadcrumbListId);
  if (!nav || !list) return;

  const crumbs = buildCrumbs(currentPath);
  list.innerHTML = "";
  if (crumbs.length <= 1) {
    nav.hidden = true;
    return;
  }

  nav.hidden = false;
  const lastIndex = crumbs.length - 1;
  crumbs.forEach(([href, label], idx) => {
    const li = document.createElement("li");
    li.className = "breadcrumb-item";

    if (idx === lastIndex) {
      li.setAttribute("aria-current", "page");
      li.textContent = String(label || "");
      list.appendChild(li);
      return;
    }

    const a = document.createElement("a");
    a.className = "breadcrumb-link";
    a.href = `#${sanitizePath(href)}`;
    a.textContent = String(label || "");
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      setAppPath(href);
    });

    li.appendChild(a);
    list.appendChild(li);
  });
}

function updateSidebarActive(currentPath, sidebarLinkSelector) {
  const links = Array.from(document.querySelectorAll(sidebarLinkSelector));
  if (!links.length) return;

  const path = sanitizePath(currentPath);

  let active = "/";
  let bestLen = 1;

  for (const el of links) {
    const href = sanitizePath(el.getAttribute("data-app-href") || "/");
    if (href === path) {
      active = href;
      bestLen = href.length;
      break;
    }
    if (href !== "/" && path.startsWith(href) && href.length > bestLen) {
      active = href;
      bestLen = href.length;
    }
  }

  for (const el of links) {
    const href = sanitizePath(el.getAttribute("data-app-href") || "/");
    const isActive = href === active;
    el.classList.toggle("active", isActive);
    if (isActive) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  }
}

function wireSidebarAppLinks(sidebarLinkSelector) {
  const links = Array.from(document.querySelectorAll(sidebarLinkSelector));
  links.forEach((el) => {
    if (el.__gustavAppLinkWired) return;
    el.__gustavAppLinkWired = true;
    el.addEventListener("click", (ev) => {
      const href = el.getAttribute("data-app-href");
      if (!href) return;
      ev.preventDefault();
      setAppPath(href);
    });
  });
}

function initSidebarLite({ sidebarId, mainId, toggleSelector, overlaySelector, storageKey }) {
  const sidebar = document.getElementById(sidebarId);
  const mainContent = document.getElementById(mainId);
  const toggleBtn = document.querySelector(toggleSelector);
  const overlay = document.querySelector(overlaySelector);

  if (!sidebar || !mainContent || !toggleBtn || !overlay) return;

  const mobileQuery = window.matchMedia("(max-width: 768px)");

  function syncAriaExpanded() {
    const isMobile = mobileQuery.matches;
    if (isMobile) {
      toggleBtn.setAttribute("aria-expanded", sidebar.classList.contains("open") ? "true" : "false");
      return;
    }
    toggleBtn.setAttribute("aria-expanded", sidebar.classList.contains("collapsed") ? "false" : "true");
  }

  function restoreDesktopState() {
    if (mobileQuery.matches) return;
    const saved = localStorage.getItem(storageKey);
    const collapsed = saved === "collapsed";
    sidebar.classList.toggle("collapsed", collapsed);
    mainContent.classList.toggle("sidebar-collapsed", collapsed);
    syncAriaExpanded();
  }

  function closeMobileSidebar() {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
    document.body.style.overflow = "";
    syncAriaExpanded();
  }

  function openMobileSidebar() {
    sidebar.classList.add("open");
    overlay.classList.add("active");
    document.body.style.overflow = "hidden";
    syncAriaExpanded();
  }

  function toggleSidebar() {
    const isMobile = mobileQuery.matches;
    if (isMobile) {
      const isOpen = sidebar.classList.contains("open");
      if (isOpen) closeMobileSidebar();
      else openMobileSidebar();
      return;
    }

    const collapsed = sidebar.classList.toggle("collapsed");
    mainContent.classList.toggle("sidebar-collapsed", collapsed);
    localStorage.setItem(storageKey, collapsed ? "collapsed" : "expanded");
    syncAriaExpanded();
  }

  toggleBtn.addEventListener("click", (ev) => {
    ev.preventDefault();
    toggleSidebar();
  });

  overlay.addEventListener("click", (ev) => {
    ev.preventDefault();
    closeMobileSidebar();
  });

  overlay.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    ev.preventDefault();
    closeMobileSidebar();
  });

  window.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    closeMobileSidebar();
  });

  mobileQuery.addEventListener("change", () => {
    closeMobileSidebar();
    restoreDesktopState();
  });

  restoreDesktopState();
}

export function initGustavDemoShell(options = {}) {
  const {
    defaultPath = FALLBACK_DEFAULT_APP_PATH,
    sidebarId = "sidebar",
    mainId = "main-content",
    toggleSelector = '[data-action="sidebar-toggle"]',
    overlaySelector = '.sidebar-overlay[data-action="sidebar-close"]',
    breadcrumbId = "breadcrumb",
    breadcrumbListId = "breadcrumb-list",
    sidebarLinkSelector = ".sidebar-items [data-app-href]",
    sidebarStorageKey = "gustav-sidebar",
  } = options || {};

  initSidebarLite({
    sidebarId,
    mainId,
    toggleSelector,
    overlaySelector,
    storageKey: sidebarStorageKey,
  });

  wireSidebarAppLinks(sidebarLinkSelector);

  if (!String(window.location.hash || "").startsWith("#/")) {
    setAppPath(defaultPath, { replace: true });
  }

  const update = () => {
    const path = getAppPathFromLocation(defaultPath);
    renderBreadcrumb(path, { breadcrumbId, breadcrumbListId });
    updateSidebarActive(path, sidebarLinkSelector);
  };

  window.addEventListener("hashchange", update);
  update();
}

