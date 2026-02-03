import { computeRuntime, createDefaultState } from "./engine.js";
import {
  GRAPH_STORAGE_KEY,
  STATE_STORAGE_KEY,
  escapeHtml,
  loadGraph,
  loadState,
  qparam,
  statusLabel,
  typeLabel,
  wireTaskCheckboxes,
  writeJsonToLocalStorage,
} from "./student-graph-common.js";

const SAMPLE_URL = "../shared/data/sample-graph.json";

function nodeById(graph, id) {
  return (graph?.nodes || []).find((n) => String(n.id) === String(id)) || null;
}

function ensureStateIncludesTasks(graph, state) {
  state.taskDone = state.taskDone && typeof state.taskDone === "object" ? state.taskDone : {};
  for (const n of graph.nodes || []) {
    for (const t of n.tasks || []) {
      const tid = String(t.id || "");
      if (!tid) continue;
      if (state.taskDone[tid] !== true && state.taskDone[tid] !== false) state.taskDone[tid] = false;
    }
  }
}

function buildCardsPreviewHtml(cards, locked) {
  const list = (cards || [])
    .slice(0, 4)
    .map((c) => {
      const front = String(c.front || "");
      const back = String(c.back || "");
      return `
        <div class="card-item ${locked ? "is-locked" : ""}">
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
    .join("");

  if (!list) return "";
  const more = (cards || []).length > 4 ? `<p class="text-muted"><small>+ ${escapeHtml(String((cards || []).length - 4))} weitere</small></p>` : "";
  return `
    <div class="hr"></div>
    <h2 class="h2">Karteikarten</h2>
    <p class="text-muted"><small>Nur Vorschau (Ueben ist ein eigener Screen).</small></p>
    <div class="cards-panel">${list}</div>
    ${more}
  `;
}

function buildModulePanelHtml(graph, runtime, state, node) {
  const id = String(node.id || "");
  const type = String(node.type || "");
  const st = runtime.statusById?.[id] || {};
  const status = statusLabel(String(st.status || "locked"));
  const tl = typeLabel(type);
  const isLocked = String(st.status || "") === "locked";
  const showTypeBadge = type === "flashcards" || type === "choice_group";

  const tasks = Array.isArray(node.tasks) ? node.tasks : [];
  const mats = Array.isArray(node.materials) ? node.materials : [];
  const cards = Array.isArray(node.cards) ? node.cards : [];

  const done = Number(st.doneTasks || 0);
  const total = Number(st.totalTasks || 0);

  const counts = [];
  if (tasks.length) counts.push(`<span class="badge">A ${escapeHtml(total > 0 ? `${done}/${total}` : String(tasks.length))}</span>`);
  if (mats.length) counts.push(`<span class="badge">M ${escapeHtml(String(mats.length))}</span>`);
  if (cards.length) counts.push(`<span class="badge">K ${escapeHtml(String(cards.length))}</span>`);

  const badgesHtml = `
    ${showTypeBadge ? `<span class="badge ${escapeHtml(tl.badge)}">${escapeHtml(tl.label)}</span>` : ""}
    <span class="badge ${escapeHtml(status.badge)}">${escapeHtml(status.label)}</span>
  `;

  const materialsHtml = mats.length
    ? `
      <div class="hr"></div>
      <h2 class="h2">Materialien</h2>
      <ul class="list">
        ${mats
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
          .join("")}
      </ul>
    `
    : "";

  const tasksHtml = tasks.length
    ? `
      <div class="hr"></div>
      <h2 class="h2">Aufgaben</h2>
      <ul class="list">
        ${tasks
          .map((t) => {
            const tid = String(t.id || "");
            const instr = String(t.instruction || "");
            const checked = state.taskDone?.[tid] === true;
            return `
              <li>
                <div class="task-row">
                  <input
                    type="checkbox"
                    data-task-id="${escapeHtml(tid)}"
                    ${checked ? "checked" : ""}
                    ${isLocked ? "disabled" : ""}
                  />
                  <span>${escapeHtml(t.title || tid)}</span>
                </div>
                ${instr ? `<div class="task-instruction text-muted"><small>${escapeHtml(instr)}</small></div>` : ""}
              </li>
            `;
          })
          .join("")}
      </ul>
      ${isLocked ? `<p class="text-muted"><small>Dieses Modul ist gesperrt.</small></p>` : ""}
    `
    : "";

  return `
    <div class="module-header">
      <div>
        <div class="module-badges">${badgesHtml}</div>
        ${counts.length ? `<div style="margin-top: var(--space-2); display: inline-flex; gap: var(--space-2); flex-wrap: wrap;">${counts.join("")}</div>` : ""}
      </div>
      <div class="text-muted"><small>Fortschritt wird lokal gespeichert.</small></div>
    </div>
    ${materialsHtml}
    ${tasksHtml}
    ${buildCardsPreviewHtml(cards, isLocked)}
  `;
}

async function main() {
  const titleEl = document.getElementById("module-title");
  const subtitleEl = document.getElementById("module-subtitle");
  const panelEl = document.getElementById("module-panel");

  if (!titleEl || !subtitleEl || !panelEl) throw new Error("missing_dom");

  const moduleId = String(qparam("id") || "");
  const source = String(qparam("source") || "");
  if (source) {
    document.querySelectorAll("a[data-preserve-source]").forEach((a) => {
      const href = String(a.getAttribute("href") || "");
      if (!href) return;
      const sep = href.includes("?") ? "&" : "?";
      a.setAttribute("href", `${href}${sep}source=${encodeURIComponent(source)}`);
    });
  }

  if (!moduleId) {
    titleEl.textContent = "Modul";
    subtitleEl.textContent = "";
    panelEl.innerHTML = `<p class="text-muted">Kein Modul angegeben.</p>`;
    return;
  }

  const graph = await loadGraph({ sampleUrl: SAMPLE_URL, storageKey: GRAPH_STORAGE_KEY });
  writeJsonToLocalStorage(GRAPH_STORAGE_KEY, graph);

  const node = nodeById(graph, moduleId);
  if (!node) {
    titleEl.textContent = "Modul";
    subtitleEl.textContent = "";
    panelEl.innerHTML = `<p class="text-muted">Unbekanntes Modul: <code>${escapeHtml(moduleId)}</code></p>`;
    return;
  }

  let state = loadState(graph, { storageKey: STATE_STORAGE_KEY });
  ensureStateIncludesTasks(graph, state);
  if (!state || typeof state !== "object") state = createDefaultState(graph);
  writeJsonToLocalStorage(STATE_STORAGE_KEY, state);

  function rerender() {
    const runtime = computeRuntime(graph, state);
    const st = runtime.statusById?.[moduleId] || {};
    const sl = statusLabel(String(st.status || "locked"));
    titleEl.textContent = String(node.title || node.id);
    document.title = `Student: ${String(node.title || node.id)}`;
    subtitleEl.innerHTML = `
      <span class="badge ${escapeHtml(sl.badge)}">${escapeHtml(sl.label)}</span>
      <span class="text-muted"><small style="margin-left: var(--space-2);">Klick auf "Zur Übersicht" um den Graph zu sehen.</small></span>
    `;

    panelEl.innerHTML = buildModulePanelHtml(graph, runtime, state, node);

    wireTaskCheckboxes(panelEl, state, () => {
      ensureStateIncludesTasks(graph, state);
      writeJsonToLocalStorage(STATE_STORAGE_KEY, state);
      rerender();
    });
  }

  rerender();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => main().catch(console.error));
} else {
  main().catch(console.error);
}
