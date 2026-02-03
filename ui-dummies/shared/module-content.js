import { escapeHtml } from "./student-graph-common.js";

export function ensureStateIncludesTasks(graph, state) {
  state.taskDone = state.taskDone && typeof state.taskDone === "object" ? state.taskDone : {};
  for (const n of graph?.nodes || []) {
    for (const t of n?.tasks || []) {
      const tid = String(t?.id || "");
      if (!tid) continue;
      if (state.taskDone[tid] !== true && state.taskDone[tid] !== false) state.taskDone[tid] = false;
    }
  }
}

export function buildCardsPreviewHtml(cards, locked, opts = {}) {
  const limit = Math.max(0, Number(opts.limit ?? 3));
  const show = (cards || []).slice(0, limit);

  const list = show
    .map((c) => {
      const front = String(c?.front || "");
      const back = String(c?.back || "");
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
  const more =
    (cards || []).length > limit
      ? `<p class="text-muted"><small>+ ${escapeHtml(String((cards || []).length - limit))} weitere</small></p>`
      : "";

  return `
    <div class="hr"></div>
    <h3>Karteikarten</h3>
    <p class="text-muted"><small>Nur Vorschau (Ueben ist ein eigener Screen).</small></p>
    <div class="cards-panel">${list}</div>
    ${more}
  `;
}

export function buildModuleBodyHtml(runtime, state, node, opts = {}) {
  const id = String(node?.id || "");
  const st = runtime?.statusById?.[id] || {};
  const locked = String(st.status || "") === "locked";

  const tasks = Array.isArray(node?.tasks) ? node.tasks : [];
  const mats = Array.isArray(node?.materials) ? node.materials : [];
  const cards = Array.isArray(node?.cards) ? node.cards : [];

  const materialsHtml = mats.length
    ? `
      <h3>Materialien</h3>
      <ul class="list">
        ${mats
          .map((m) => {
            const title = String(m?.title || m?.id || "");
            const summary = String(m?.summary || "");
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
      <h3>Aufgaben</h3>
      <ul class="list">
        ${tasks
          .map((t) => {
            const tid = String(t?.id || "");
            const instr = String(t?.instruction || "");
            const checked = state?.taskDone?.[tid] === true;
            return `
              <li>
                <div class="task-row">
                  <input
                    type="checkbox"
                    data-task-id="${escapeHtml(tid)}"
                    ${checked ? "checked" : ""}
                    ${locked ? "disabled" : ""}
                  />
                  <span>${escapeHtml(t?.title || tid)}</span>
                </div>
                ${instr ? `<div class="task-instruction text-muted"><small>${escapeHtml(instr)}</small></div>` : ""}
              </li>
            `;
          })
          .join("")}
      </ul>
      ${locked ? `<p class="text-muted"><small>Dieses Modul ist gesperrt.</small></p>` : ""}
    `
    : "";

  const cardsLimit = Number(opts.cardsPreviewLimit ?? 3);
  const cardsHtml = buildCardsPreviewHtml(cards, locked, { limit: cardsLimit });

  return `
    ${materialsHtml}
    ${tasksHtml}
    ${cardsHtml}
  `;
}

