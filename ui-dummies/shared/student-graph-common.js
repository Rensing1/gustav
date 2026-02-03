import { clamp01, createDefaultState, formatPercent01 } from "./engine.js";

export const GRAPH_STORAGE_KEY = "ui-dummy:graph";
export const STATE_STORAGE_KEY = "ui-dummy:state";

export function qparam(name) {
  return new URLSearchParams(window.location.search || "").get(name);
}

export function readJsonFromLocalStorage(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

export function writeJsonToLocalStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    // ignore
  }
}

export async function fetchGraphFromSample(sampleUrl) {
  const resp = await fetch(String(sampleUrl || ""), { cache: "no-store" });
  if (!resp.ok) throw new Error(`graph_fetch_failed_${resp.status}`);
  return await resp.json();
}

export async function loadGraph({ sampleUrl, storageKey = GRAPH_STORAGE_KEY } = {}) {
  const source = qparam("source") || "";
  if (source === "localStorage") {
    const g = readJsonFromLocalStorage(storageKey);
    if (g && typeof g === "object") return g;
  }
  return await fetchGraphFromSample(sampleUrl);
}

export function loadState(graph, { storageKey = STATE_STORAGE_KEY } = {}) {
  const s = readJsonFromLocalStorage(storageKey);
  if (s && typeof s === "object") {
    // Minimal shape validation (keep it permissive).
    if (!s.taskDone || typeof s.taskDone !== "object") s.taskDone = {};
    if (!s.deckBaseStrength || typeof s.deckBaseStrength !== "object") s.deckBaseStrength = {};
    if (!Number.isFinite(Number(s.days))) s.days = 0;
    return s;
  }
  return createDefaultState(graph);
}

export function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj || null));
}

export function escapeHtml(s) {
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function truncateText(input, maxLen) {
  const s = String(input || "");
  const n = Math.max(0, Number(maxLen || 0));
  if (!n) return "";
  if (s.length <= n) return s;
  if (n <= 3) return s.slice(0, n);
  return `${s.slice(0, n - 3)}...`;
}

export function cssVar(name, fallback = "") {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(String(name || "")).trim();
    return v || String(fallback || "");
  } catch (_) {
    return String(fallback || "");
  }
}

export function getThemeColors() {
  return {
    bgBase: cssVar("--color-bg-base", "#ffffff"),
    bgSurface: cssVar("--color-bg-surface", "#ffffff"),
    bgOverlay: cssVar("--color-bg-overlay", "#f0f0f0"),
    text: cssVar("--color-text", "#111111"),
    textMuted: cssVar("--color-text-muted", "#666666"),
    primary: cssVar("--color-primary", "#286983"),
    warning: cssVar("--color-warning", "#ea9d34"),
    success: cssVar("--color-success", "#56949f"),
    border: cssVar("--color-border", "#dddddd"),
  };
}

export function formatNodeOverviewLabel(graph, runtime, node, opts = {}) {
  const id = String(node?.id || "");
  const type = String(node?.type || "");
  const titleMax = Math.max(10, Number(opts.titleMax || 28));
  const title = truncateText(String(node?.title || id), titleMax);
  const st = runtime?.statusById?.[id] || {};

  if (type === "flashcards") {
    const eff = clamp01(Number(st.strength ?? 0));
    const target = clamp01(Number(node?.targetStrength ?? 0));
    return `${title}\nDeck ${Math.round(eff * 100)}% (Ziel ${Math.round(target * 100)}%)`;
  }

  const done = Number(st.doneTasks || 0);
  const total = Number(st.totalTasks || 0);
  const tasksLen = Array.isArray(node?.tasks) ? node.tasks.length : 0;
  const mats = Array.isArray(node?.materials) ? node.materials.length : 0;
  const cards = Array.isArray(node?.cards) ? node.cards.length : 0;

  const parts = [];
  const effectiveTotal = total > 0 ? total : tasksLen;
  if (effectiveTotal > 0) parts.push(`A ${Math.min(done, effectiveTotal)}/${effectiveTotal}`);
  if (mats > 0) parts.push(`M ${mats}`);
  if (cards > 0) parts.push(`K ${cards}`);

  if (!parts.length) return title;
  return `${title}\n${parts.join(" · ")}`;
}

export function typeLabel(type) {
  if (type === "flashcards") return { label: "Karteikarten", badge: "badge-primary" };
  if (type === "choice_group") return { label: "Wahlpflicht-Gruppe", badge: "badge-warning" };
  return { label: "Modul", badge: "" };
}

export function statusLabel(status) {
  if (status === "locked") return { label: "gesperrt", badge: "" };
  if (status === "open") return { label: "offen", badge: "badge-primary" };
  if (status === "partial") return { label: "teilweise", badge: "badge-warning" };
  if (status === "done") return { label: "fertig", badge: "badge-success" };
  return { label: status || "?", badge: "" };
}

function nodeTitleById(graph, id) {
  const n = (graph.nodes || []).find((x) => String(x.id) === String(id));
  return n ? String(n.title || n.id) : String(id);
}

function deckById(graph, id) {
  return (graph.decks || []).find((d) => String(d.id) === String(id)) || null;
}

function unitTitle(graph) {
  const m = graph && graph.meta && typeof graph.meta === "object" ? graph.meta : null;
  return m && m.title ? String(m.title) : "Lerneinheit";
}

export function collectCardEntries(graph, runtime) {
  const out = [];
  const unit = unitTitle(graph);

  for (const node of graph.nodes || []) {
    const type = String(node.type || "");
    if (type === "choice_group") continue;
    const cards = Array.isArray(node.cards) ? node.cards : [];
    if (!cards.length) continue;
    const st = (runtime.statusById || {})[String(node.id)] || {};
    const locked = String(st.status || "") === "locked";
    for (const c of cards) {
      out.push({
        id: String(c.id || ""),
        front: String(c.front || ""),
        back: String(c.back || ""),
        unitTitle: unit,
        moduleId: String(node.id || ""),
        moduleTitle: String(node.title || node.id || ""),
        locked,
      });
    }
  }

  const lib = Array.isArray(graph.libraryCards) ? graph.libraryCards : [];
  for (const c of lib) {
    out.push({
      id: String(c.id || ""),
      front: String(c.front || ""),
      back: String(c.back || ""),
      unitTitle: String(c.unitTitle || "Andere Einheit"),
      moduleId: null,
      moduleTitle: String(c.moduleTitle || "Extern"),
      locked: false,
    });
  }

  return out.filter((e) => e.id);
}

export function normalizeQuery(q) {
  return String(q || "").trim().toLowerCase();
}

export function shuffleInPlace(arr) {
  for (let i = arr.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }
}

export function cssEscapeId(id) {
  const raw = String(id || "");
  if (typeof CSS !== "undefined" && CSS && typeof CSS.escape === "function") return CSS.escape(raw);
  return raw.replace(/[^a-zA-Z0-9_-]/g, (m) => `\\${m}`);
}

function renderCondition(graph, runtime, cond) {
  const t = String(cond?.type || "");
  if (t === "moduleCompleted") {
    const mid = String(cond.moduleId || "");
    const ok = runtime.completedById[mid] === true;
    return { ok, text: `Modul abgeschlossen: ${nodeTitleById(graph, mid)}` };
  }
  if (t === "choiceGroupCompleted") {
    const gid = String(cond.groupId || "");
    const ok = runtime.completedById[gid] === true;
    return { ok, text: `Wahlpflicht erfuellt: ${nodeTitleById(graph, gid)}` };
  }
  if (t === "deckStrengthAtLeast") {
    const deckId = String(cond.deckId || "");
    const thr = clamp01(Number(cond.threshold || 0));
    const eff = Number(runtime.deckStrength[deckId] || 0);
    const dk = deckById(graph, deckId);
    const name = dk ? String(dk.title || dk.id) : deckId;
    const ok = eff >= thr;
    return {
      ok,
      text: `Karteikarten: ${name} >= ${Math.round(thr * 100)}% (aktuell ${Math.round(eff * 100)}%)`,
    };
  }
  return { ok: false, text: "Unbekannte Bedingung" };
}

export function buildNodeDetailsHtml(graph, runtime, state, nodeId) {
  const node = (graph.nodes || []).find((n) => String(n.id) === String(nodeId));
  if (!node) return `<p class="text-muted">Unbekannter Knoten.</p>`;
  const type = String(node.type || "");
  const st = runtime.statusById[String(node.id)] || {};
  const status = statusLabel(String(st.status || ""));
  const tl = typeLabel(type);
  const isLocked = String(st.status || "") === "locked";
  const cards = Array.isArray(node.cards) ? node.cards : [];

  const badges = [
    `<span class="badge ${escapeHtml(tl.badge)}">${escapeHtml(tl.label)}</span>`,
    `<span class="badge ${escapeHtml(status.badge)}">${escapeHtml(status.label)}</span>`,
  ].join(" ");

  let progressLine = "—";
  if (type === "choice_group") {
    const gp = runtime.choiceGroupProgress[String(node.id)] || { required: 0, doneMembers: 0 };
    progressLine = `${Number(gp.doneMembers || 0)} / ${Number(gp.required || 0)} abgeschlossen`;
  } else if (type === "flashcards") {
    const deckId = String(node.deckId || "");
    const eff = clamp01(Number(runtime.deckStrength[deckId] || 0));
    const target = clamp01(Number(node.targetStrength || 0));
    progressLine = `${escapeHtml(formatPercent01(eff))} (Ziel ${escapeHtml(formatPercent01(target))})`;
  } else {
    const done = Number(st.doneTasks || 0);
    const total = Number(st.totalTasks || 0);
    progressLine = total > 0 ? `${done}/${total} Aufgaben` : "Material-only";
  }

  let prereqHtml = "";
  if (node.requires && typeof node.requires === "object") {
    const req = node.requires;
    const list = Array.isArray(req.all) ? req.all : Array.isArray(req.any) ? req.any : [];
    if (list.length) {
      const items = list
        .map((c) => {
          const r = renderCondition(graph, runtime, c);
          const mark = r.ok ? "[x]" : "[ ]";
          return `<li>${escapeHtml(mark)} ${escapeHtml(r.text)}</li>`;
        })
        .join("");
      prereqHtml = `
        <div class="hr"></div>
        <h3>Voraussetzungen</h3>
        <ul class="list">${items}</ul>
      `;
    }
  }

  let materialsHtml = "";
  const mats = Array.isArray(node.materials) ? node.materials : [];
  if (mats.length) {
    const items = mats
      .map((m) => {
        const title = String(m.title || m.id || "");
        const summary = String(m.summary || "");
        return `
          <li>
            <div><strong>${escapeHtml(title)}</strong></div>
            ${summary ? `<div class="text-muted material-summary"><small>${escapeHtml(summary)}</small></div>` : ""}
          </li>
        `;
      })
      .join("");
    materialsHtml = `
      <div class="hr"></div>
      <h3>Materialien</h3>
      <ul class="list">${items}</ul>
    `;
  }

  let tasksHtml = "";
  const tasks = Array.isArray(node.tasks) ? node.tasks : [];
  if (tasks.length) {
    const disabled = isLocked;
    const items = tasks
      .map((t) => {
        const tid = String(t.id);
        const instr = String(t.instruction || "");
        const checked = state.taskDone[tid] === true;
        const disAttr = disabled ? "disabled" : "";
        return `
          <li>
            <div class="task-row">
              <input type="checkbox" data-task-id="${escapeHtml(tid)}" ${checked ? "checked" : ""} ${disAttr} />
              <span>${escapeHtml(t.title || tid)}</span>
            </div>
            ${instr ? `<div class="task-instruction text-muted"><small>${escapeHtml(instr)}</small></div>` : ""}
          </li>
        `;
      })
      .join("");
    tasksHtml = `
      <div class="hr"></div>
      <h3>Aufgaben</h3>
      <ul class="list">${items}</ul>
      ${disabled ? `<p class="text-muted"><small>Aufgaben sind gesperrt, solange das Modul gesperrt ist.</small></p>` : ""}
    `;
  }

  let cardsHtml = "";
  if (cards.length && type !== "choice_group" && type !== "flashcards") {
    const limit = 3;
    const show = cards.slice(0, limit);
    const items = show
      .map((c) => {
        const front = String(c.front || "");
        const back = String(c.back || "");
        return `
          <div class="card-item ${isLocked ? "is-locked" : "is-unlocked"}">
            <div class="card-item__front">${escapeHtml(front || "(ohne Front)")}</div>
            ${
              isLocked
                ? `<div class="card-item__back is-hidden"><small>Antwort gesperrt.</small></div>`
                : `
                  <details>
                    <summary><small>Antwort anzeigen</small></summary>
                    <div class="card-item__back">${escapeHtml(back || "(ohne Back)")}</div>
                  </details>
                `
            }
          </div>
        `;
      })
      .join("");
    cardsHtml = `
      <div class="hr"></div>
      <h3>Karteikarten</h3>
      <p class="text-muted"><small>Vorschau.</small></p>
      <div class="cards-panel">${items}</div>
      ${cards.length > limit ? `<p class="text-muted"><small>+ ${escapeHtml(String(cards.length - limit))} weitere</small></p>` : ""}
      <button class="btn btn-secondary btn-cards" type="button" data-open-cards-module="${escapeHtml(String(node.id))}">Alle Karten anzeigen</button>
      ${isLocked ? `<p class="text-muted"><small>Hinweis: Gesperrt -> Antworten bleiben verborgen.</small></p>` : ""}
    `;
  }

  let groupHtml = "";
  if (type === "choice_group") {
    const choice = node.choice || {};
    const members = Array.isArray(choice.memberIds) ? choice.memberIds.map(String) : [];
    const reqN = Math.max(0, Number(choice.n || 0));
    const items = members
      .map((mid) => {
        const ms = runtime.statusById[String(mid)] || {};
        const sl = statusLabel(String(ms.status || "locked"));
        return `
          <li>
            <button class="btn btn-secondary" type="button" data-jump-node="${escapeHtml(mid)}">
              ${escapeHtml(nodeTitleById(graph, mid))}
            </button>
            <span class="badge ${escapeHtml(sl.badge)}" style="margin-left: var(--space-2);">${escapeHtml(sl.label)}</span>
          </li>
        `;
      })
      .join("");
    groupHtml = `
      <div class="hr"></div>
      <h3>Wahlpflicht</h3>
      <p class="text-muted"><small>Regel: ${escapeHtml(String(reqN))} aus ${escapeHtml(String(members.length))} abschliessen.</small></p>
      <ul class="list">${items}</ul>
    `;
  }

  let flashcardsHtml = "";
  if (type === "flashcards") {
    const deckId = String(node.deckId || "");
    const dk = deckById(graph, deckId);
    const base = clamp01(Number((state.deckBaseStrength || {})[deckId] ?? 0));
    const eff = clamp01(Number(runtime.deckStrength[deckId] || 0));
    flashcardsHtml = `
      <div class="hr"></div>
      <h3>Karteikarten</h3>
      <div class="kv">
        <div><small>Deck</small></div>
        <div>${escapeHtml(dk ? dk.title : deckId)}</div>
        <div><small>Basis</small></div>
        <div>${escapeHtml(formatPercent01(base))}</div>
        <div><small>Effektiv</small></div>
        <div>${escapeHtml(formatPercent01(eff))}</div>
      </div>
    `;
  }

  const done = Number(st.doneTasks || 0);
  const total = Number(st.totalTasks || 0);
  const metaBadges = [];
  if (mats.length)
    metaBadges.push(
      `<span class="badge badge-meta badge-meta--materials" title="Materialien">${escapeHtml(String(mats.length))}</span>`
    );
  if (tasks.length)
    metaBadges.push(
      `<span class="badge badge-meta badge-meta--tasks" title="Aufgaben">${escapeHtml(
        total > 0 ? `${done}/${total}` : String(tasks.length)
      )}</span>`
    );
  if (cards.length)
    metaBadges.push(
      `<span class="badge badge-meta badge-meta--cards" title="Karteikarten">${escapeHtml(String(cards.length))}</span>`
    );
  const metaBadgesHtml = metaBadges.join(" ");

  return `
    <div class="floating-card__title">
      <div>
        <h3 style="margin: 0;">${escapeHtml(node.title || node.id)}</h3>
        <div style="margin-top: var(--space-2); display: flex; gap: var(--space-2); flex-wrap: wrap;">${badges}</div>
        ${metaBadges.length ? `<div style="margin-top: var(--space-2); display: flex; gap: var(--space-2); flex-wrap: wrap;">${metaBadgesHtml}</div>` : ""}
      </div>
    </div>
    <div class="kv" style="margin-top: var(--space-3);">
      <div><small>Fortschritt</small></div>
      <div>${escapeHtml(progressLine)}</div>
    </div>
    ${prereqHtml}
    ${groupHtml}
    ${materialsHtml}
    ${tasksHtml}
    ${cardsHtml}
    ${flashcardsHtml}
  `;
}

export function wireTaskCheckboxes(root, state, onChange) {
  const boxes = root.querySelectorAll('input[type="checkbox"][data-task-id]');
  boxes.forEach((cb) => {
    if (cb.__wired) return;
    cb.__wired = true;
    cb.addEventListener("change", () => {
      const tid = String(cb.getAttribute("data-task-id") || "");
      state.taskDone[tid] = cb.checked === true;
      onChange();
    });
  });
}

export function wireJumpButtons(root, onJump) {
  const btns = root.querySelectorAll("button[data-jump-node]");
  btns.forEach((btn) => {
    if (btn.__wired) return;
    btn.__wired = true;
    btn.addEventListener("click", () => {
      const id = String(btn.getAttribute("data-jump-node") || "");
      onJump(id);
    });
  });
}

export function createCardsDrawerController(opts) {
  const drawerEl = opts?.drawerEl;
  const toggleBtn = opts?.toggleBtn;
  const closeBtn = opts?.closeBtn;
  const panelEl = opts?.panelEl;
  const searchInputEl = opts?.searchInputEl;
  const shuffleBtnEl = opts?.shuffleBtnEl;
  const closeOtherDrawers = typeof opts?.closeOtherDrawers === "function" ? opts.closeOtherDrawers : () => {};
  const getGraph = typeof opts?.getGraph === "function" ? opts.getGraph : () => null;
  const getRuntime = typeof opts?.getRuntime === "function" ? opts.getRuntime : () => null;

  if (!drawerEl || !panelEl || !searchInputEl || !shuffleBtnEl) {
    throw new Error("cards_drawer_missing_dom");
  }

  let cardsMode = "mixed";
  let cardsQuery = "";
  let cardsFocusModuleId = null;
  let mixedOrder = [];

  function isOpen() {
    return drawerEl.hidden === false;
  }

  function updateCardsModeButtons() {
    const btns = drawerEl.querySelectorAll("button[data-cards-mode]");
    btns.forEach((btn) => {
      const mode = String(btn.getAttribute("data-cards-mode") || "");
      const active = mode === cardsMode;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function ensureMixedOrder(entries) {
    const ids = entries.map((e) => e.id).filter(Boolean);
    if (!ids.length) {
      mixedOrder = [];
      return;
    }
    const same = mixedOrder.length === ids.length && mixedOrder.every((id) => ids.includes(id));
    if (!same) {
      mixedOrder = ids.slice();
      shuffleInPlace(mixedOrder);
    }
  }

  function setOpen(open, opts2 = {}) {
    drawerEl.hidden = open !== true;
    if (toggleBtn) toggleBtn.setAttribute("aria-expanded", open === true ? "true" : "false");

    if (open === true) {
      cardsFocusModuleId = String(opts2.focusModuleId || "") || null;
      cardsMode = String(opts2.mode || cardsMode || "mixed");
      updateCardsModeButtons();
      searchInputEl.value = cardsQuery || "";
      try {
        searchInputEl.focus({ preventScroll: true });
      } catch (_) {}
      render();
    } else {
      cardsFocusModuleId = null;
    }
  }

  function render() {
    if (drawerEl.hidden === true) return;
    const graph = getGraph();
    const runtime = getRuntime();
    if (!graph || !runtime) return;

    updateCardsModeButtons();

    const q = normalizeQuery(cardsQuery);
    const all = collectCardEntries(graph, runtime);

    const filtered = q
      ? all.filter((e) => {
          const hay = `${e.front} ${e.back} ${e.moduleTitle} ${e.unitTitle}`.toLowerCase();
          return hay.includes(q);
        })
      : all.slice();

    const orderIndex = new Map();
    ensureMixedOrder(all);
    for (let i = 0; i < mixedOrder.length; i += 1) orderIndex.set(mixedOrder[i], i);

    if (cardsMode === "mixed") {
      filtered.sort((a, b) => (orderIndex.get(a.id) ?? 999999) - (orderIndex.get(b.id) ?? 999999));
      panelEl.innerHTML = filtered.length
        ? filtered
            .map((e) => {
              const locked = e.locked === true;
              const classes = [
                "card-item",
                locked ? "is-locked" : "is-unlocked",
                cardsFocusModuleId && String(e.moduleId || "") === String(cardsFocusModuleId) ? "is-focused" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return `
                <div class="${escapeHtml(classes)}" data-card-id="${escapeHtml(e.id)}">
                  <div class="card-item__meta">
                    <span class="card-item__where">${escapeHtml(`${e.unitTitle} / ${e.moduleTitle}`)}</span>
                    <span class="badge ${locked ? "" : "badge-primary"}">${escapeHtml(locked ? "gesperrt" : "frei")}</span>
                  </div>
                  <div class="card-item__front">${escapeHtml(e.front || "(ohne Front)")}</div>
                  ${
                    locked
                      ? `<div class="card-item__back is-hidden"><small>Antwort gesperrt.</small></div>`
                      : `
                        <details>
                          <summary><small>Antwort anzeigen</small></summary>
                          <div class="card-item__back">${escapeHtml(e.back || "(ohne Back)")}</div>
                        </details>
                      `
                  }
                </div>
              `;
            })
            .join("")
        : `<p class="text-muted"><small>Keine Karten gefunden.</small></p>`;
      return;
    }

    // cardsMode === "modules"
    const blocks = [];
    for (const n of graph.nodes || []) {
      if (String(n.type || "") === "choice_group") continue;
      const cards = Array.isArray(n.cards) ? n.cards : [];
      if (!cards.length) continue;

      const st = (runtime.statusById || {})[String(n.id)] || {};
      const locked = String(st.status || "") === "locked";
      const sl = statusLabel(String(st.status || "locked"));

      const list = cards
        .map((c) => {
          const front = String(c.front || "");
          const back = String(c.back || "");
          const match = !q || `${front} ${back} ${String(n.title || "")}`.toLowerCase().includes(q);
          if (!match) return "";
          return `
            <div class="card-item ${locked ? "is-locked" : "is-unlocked"}">
              <div class="card-item__front">${escapeHtml(front || "(ohne Front)")}</div>
              ${
                locked
                  ? `<div class="card-item__back is-hidden"><small>Antwort gesperrt.</small></div>`
                  : `
                    <details>
                      <summary><small>Antwort anzeigen</small></summary>
                      <div class="card-item__back">${escapeHtml(back || "(ohne Back)")}</div>
                    </details>
                  `
              }
            </div>
          `;
        })
        .filter(Boolean)
        .join("");

      if (!list) continue;

      blocks.push(`
        <section class="module-block ${locked ? "" : "is-unlocked"}" id="module-block-${escapeHtml(String(n.id))}">
          <h3 class="module-block__title">${escapeHtml(String(n.title || n.id))}</h3>
          <div class="module-block__meta">
            <span class="badge ${escapeHtml(sl.badge)}">${escapeHtml(sl.label)}</span>
            <span class="badge">${escapeHtml(`K ${cards.length}`)}</span>
          </div>
          <div class="hr"></div>
          <div class="cards-panel">${list}</div>
        </section>
      `);
    }

    const ext = (Array.isArray(graph.libraryCards) ? graph.libraryCards : []).slice();
    const extMatch = q
      ? ext.filter((c) => `${c.front} ${c.back} ${c.unitTitle} ${c.moduleTitle}`.toLowerCase().includes(q))
      : ext;
    if (extMatch.length) {
      const extItems = extMatch
        .map((c) => {
          return `
            <div class="card-item is-unlocked">
              <div class="card-item__meta">
                <span class="card-item__where">${escapeHtml(`${c.unitTitle} / ${c.moduleTitle}`)}</span>
                <span class="badge badge-primary">frei</span>
              </div>
              <div class="card-item__front">${escapeHtml(String(c.front || "(ohne Front)"))}</div>
              <details>
                <summary><small>Antwort anzeigen</small></summary>
                <div class="card-item__back">${escapeHtml(String(c.back || "(ohne Back)"))}</div>
              </details>
            </div>
          `;
        })
        .join("");

      blocks.push(`
        <section class="module-block is-unlocked">
          <h3 class="module-block__title">Andere Einheiten</h3>
          <div class="module-block__meta">
            <span class="badge">${escapeHtml(`K ${extMatch.length}`)}</span>
          </div>
          <div class="hr"></div>
          <div class="cards-panel">${extItems}</div>
        </section>
      `);
    }

    panelEl.innerHTML = blocks.length ? blocks.join("") : `<p class="text-muted"><small>Keine Karten gefunden.</small></p>`;

    if (cardsFocusModuleId) {
      const el = panelEl.querySelector(`#module-block-${cssEscapeId(cardsFocusModuleId)}`);
      if (el) el.scrollIntoView({ block: "start" });
    }
  }

  function wireOpenButtons(root) {
    const btns = root.querySelectorAll("button[data-open-cards-module]");
    btns.forEach((btn) => {
      if (btn.__wired) return;
      btn.__wired = true;
      btn.addEventListener("click", () => {
        const id = String(btn.getAttribute("data-open-cards-module") || "");
        if (!id) return;
        closeOtherDrawers();
        setOpen(true, { focusModuleId: id, mode: "modules" });
        render();
      });
    });
  }

  if (toggleBtn && !toggleBtn.__wiredCards) {
    toggleBtn.__wiredCards = true;
    toggleBtn.addEventListener("click", () => {
      closeOtherDrawers();
      const opening = drawerEl.hidden === true;
      setOpen(opening, opening ? { mode: "mixed" } : {});
    });
  }
  if (closeBtn && !closeBtn.__wiredCards) {
    closeBtn.__wiredCards = true;
    closeBtn.addEventListener("click", () => setOpen(false));
  }

  const modeBtns = drawerEl.querySelectorAll("button[data-cards-mode]");
  modeBtns.forEach((btn) => {
    if (btn.__wiredCardsMode) return;
    btn.__wiredCardsMode = true;
    btn.addEventListener("click", () => {
      cardsMode = String(btn.getAttribute("data-cards-mode") || "mixed");
      render();
    });
  });

  if (!searchInputEl.__wiredCardsSearch) {
    searchInputEl.__wiredCardsSearch = true;
    searchInputEl.addEventListener("input", () => {
      cardsQuery = String(searchInputEl.value || "");
      render();
    });
  }

  if (!shuffleBtnEl.__wiredCardsShuffle) {
    shuffleBtnEl.__wiredCardsShuffle = true;
    shuffleBtnEl.addEventListener("click", () => {
      const graph = getGraph();
      const runtime = getRuntime();
      if (!graph || !runtime) return;
      const all = collectCardEntries(graph, runtime);
      mixedOrder = all.map((e) => e.id).filter(Boolean);
      shuffleInPlace(mixedOrder);
      render();
    });
  }

  return {
    isOpen,
    setOpen,
    render,
    wireOpenButtons,
    close: () => setOpen(false),
  };
}

export function renderStatePanel(panel, graph, runtime, state, onChange) {
  const days = Math.max(0, Number(state.days || 0));

  const decks = graph.decks || [];
  const deckBlocks = decks
    .map((d) => {
      const deckId = String(d.id);
      const base = clamp01(Number((state.deckBaseStrength || {})[deckId] ?? 0));
      const eff = clamp01(Number(runtime.deckStrength[deckId] || 0));
      const decay = Math.max(0, Number(d.decayPerDay || 0));
      return `
        <div class="row">
          <label for="deck-${escapeHtml(deckId)}">${escapeHtml(String(d.title || deckId))}</label>
          <div class="kv">
            <div><small>Basis</small></div>
            <div>${escapeHtml(formatPercent01(base))}</div>
            <div><small>Effektiv</small></div>
            <div>${escapeHtml(formatPercent01(eff))}</div>
            <div><small>Decay/Tag</small></div>
            <div>${escapeHtml(String(decay))}</div>
          </div>
          <input
            id="deck-${escapeHtml(deckId)}"
            type="range"
            min="0"
            max="1"
            step="0.01"
            value="${escapeHtml(String(base))}"
            data-deck-id="${escapeHtml(deckId)}"
          />
        </div>
      `;
    })
    .join("");

  panel.innerHTML = `
    <div class="row">
      <label for="days">Zeit (Tage seit letzter Wiederholung)</label>
      <div class="kv">
        <div><small>Tage</small></div>
        <div>${escapeHtml(String(days))}</div>
      </div>
      <input id="days" type="range" min="0" max="30" step="1" value="${escapeHtml(String(days))}" />
      <p class="text-muted"><small>Effektiv = Basis * exp(-decay * Tage)</small></p>
    </div>
    <div class="hr"></div>
    ${deckBlocks || '<p class="text-muted">Keine Decks.</p>'}
  `;

  const daysInput = panel.querySelector("#days");
  if (daysInput && !daysInput.__wired) {
    daysInput.__wired = true;
    daysInput.addEventListener("input", () => {
      state.days = Number(daysInput.value || 0);
      onChange();
    });
  }

  const deckInputs = panel.querySelectorAll('input[type="range"][data-deck-id]');
  deckInputs.forEach((inp) => {
    if (inp.__wired) return;
    inp.__wired = true;
    inp.addEventListener("input", () => {
      const deckId = String(inp.getAttribute("data-deck-id") || "");
      state.deckBaseStrength[deckId] = clamp01(Number(inp.value || 0));
      onChange();
    });
  });
}

export function computeVisibleEdgesWithoutChoiceNodes(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const nodeById = new Map(nodes.map((n) => [String(n.id), n]));
  const raw = Array.isArray(graph?.edges) ? graph.edges : [];

  const groupNodes = nodes.filter((n) => String(n.type || "") === "choice_group");
  const groupIds = new Set(groupNodes.map((n) => String(n.id)));

  const out = [];
  const seen = new Set();

  function addEdge(fromId, toId) {
    const f = String(fromId || "");
    const t = String(toId || "");
    if (!f || !t) return;
    if (!nodeById.get(f) || !nodeById.get(t)) return;
    const key = `${f}::${t}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ from: f, to: t });
  }

  // Keep edges that do not involve group nodes.
  for (const e of raw) {
    const fromId = String(e.from || "");
    const toId = String(e.to || "");
    if (!fromId || !toId) continue;
    if (groupIds.has(fromId) || groupIds.has(toId)) continue;
    addEdge(fromId, toId);
  }

  // Expand group nodes into branch+join edges (no extra nodes).
  for (const g of groupNodes) {
    const gid = String(g.id);
    const choice = g.choice || {};
    const members = Array.isArray(choice.memberIds) ? choice.memberIds.map(String) : [];
    const memberSet = new Set(members);

    const sources = raw
      .filter((e) => String(e.to || "") === gid)
      .map((e) => String(e.from || ""))
      .filter((id) => id && !groupIds.has(id));

    const targets = raw
      .filter((e) => String(e.from || "") === gid)
      .map((e) => String(e.to || ""))
      .filter((id) => id && !groupIds.has(id) && !memberSet.has(id));

    for (const s of sources) {
      for (const m of members) addEdge(s, m);
    }
    for (const m of members) {
      for (const t of targets) addEdge(m, t);
    }
  }

  return out;
}
