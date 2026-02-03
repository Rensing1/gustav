import { computeRuntime, createDefaultState } from "../shared/engine.js";
import { initGustavDemoShell } from "../shared/gustav-demo-shell.js";
import { createGraphView } from "../shared/graph-view.js";
import { buildModuleBodyHtml, ensureStateIncludesTasks } from "../shared/module-content.js";
import {
  GRAPH_STORAGE_KEY,
  STATE_STORAGE_KEY,
  cssEscapeId,
  escapeHtml,
  loadGraph,
  loadState,
  statusLabel,
  wireTaskCheckboxes,
  writeJsonToLocalStorage,
} from "../shared/student-graph-common.js";

const SAMPLE_URL = "../shared/data/sample-graph.json";

function nodeById(graph, id) {
  return (graph?.nodes || []).find((n) => String(n.id) === String(id)) || null;
}

function compareNodeIdsByGraphOrder(graph, aId, bId) {
  const a = nodeById(graph, aId);
  const b = nodeById(graph, bId);
  if (!a && !b) return String(aId).localeCompare(String(bId), "de");
  if (!a) return 1;
  if (!b) return -1;

  const phases = Array.isArray(graph?.phases) ? graph.phases : [];
  const phaseOrder = new Map(phases.map((p, idx) => [String(p.id || ""), idx]));

  const pa = String(a.phaseId || "");
  const pb = String(b.phaseId || "");
  const ia = phaseOrder.get(pa) ?? 9999;
  const ib = phaseOrder.get(pb) ?? 9999;
  if (ia !== ib) return ia - ib;

  const xa = Number(a.x || 0);
  const xb = Number(b.x || 0);
  if (xa !== xb) return xa - xb;

  const ya = Number(a.y || 0);
  const yb = Number(b.y || 0);
  if (ya !== yb) return ya - yb;

  return String(aId).localeCompare(String(bId), "de");
}

function metaBadge(label, className, title) {
  return `<span class="badge badge-meta ${escapeHtml(className)}" title="${escapeHtml(title || "")}">${escapeHtml(label)}</span>`;
}

function sortNodesWithinPhase(nodes) {
  // Match the graph: left-to-right ordering within the same phase.
  return [...nodes].sort((a, b) => Number(a?.x || 0) - Number(b?.x || 0));
}

function isBonusModule(node) {
  const title = String(node?.title || "");
  return title.toLowerCase().startsWith("bonus");
}

function tabDotClass(status) {
  const st = String(status || "locked");
  if (st === "done") return "tab__dot tab__dot--done";
  // Keep "partial" visually identical to "open" (progress is shown via counts, not status color).
  if (st === "partial") return "tab__dot tab__dot--open";
  if (st === "open") return "tab__dot tab__dot--open";
  return "tab__dot tab__dot--locked";
}

function clampNumber(x, lo, hi) {
  const n = Number(x);
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}

function computePanGutterPx({ width, height }) {
  const base = Math.round(Math.min(Number(width || 0), Number(height || 0)) * 0.08);
  return clampNumber(base, 24, 96);
}

function findHomeNode(graph) {
  if (!graph || !Array.isArray(graph.nodes)) return null;

  const phases = Array.isArray(graph.phases) ? graph.phases : [];
  const phaseOrder = new Map(phases.map((p, idx) => [String(p.id || ""), idx]));

  let best = null;
  for (const n of graph.nodes) {
    const type = String(n?.type || "");
    if (type === "choice_group") continue;
    if (type === "flashcards") continue;

    const pid = String(n?.phaseId || "");
    const pIdx = phaseOrder.get(pid) ?? 9999;
    const x = Number(n?.x || 0);
    const y = Number(n?.y || 0);

    if (!best) {
      best = { node: n, pIdx, x, y };
      continue;
    }

    if (pIdx !== best.pIdx) {
      if (pIdx < best.pIdx) best = { node: n, pIdx, x, y };
      continue;
    }

    if (y !== best.y) {
      if (y < best.y) best = { node: n, pIdx, x, y };
      continue;
    }

    if (x !== best.x) {
      if (x < best.x) best = { node: n, pIdx, x, y };
      continue;
    }
  }

  return best?.node || null;
}

function main() {
  initGustavDemoShell();

  const graphLayer = document.getElementById("graph-layer");
  const graphShell = document.getElementById("graph-shell");
  const btnViewOverview = document.getElementById("btn-view-overview");
  const btnViewContent = document.getElementById("btn-view-content");
  const btnReset = document.getElementById("btn-reset-state");
  const viewOverview = document.getElementById("view-overview");
  const viewContent = document.getElementById("view-content");
  const contentRoot = document.getElementById("content-root");
  const unitTitleEl = document.getElementById("unit-title");

  const openTabsEl = document.getElementById("open-tabs");

  if (
    !graphLayer ||
    !graphShell ||
    !btnViewOverview ||
    !btnViewContent ||
    !btnReset ||
    !viewOverview ||
    !viewContent ||
    !contentRoot ||
    !unitTitleEl ||
    !openTabsEl
  ) {
    throw new Error("missing_dom");
  }

  let graph = null;
  let state = null;
  let runtime = null;
  let viewMode = "overview";

  const moduleEls = new Map(); // id -> { root, summary, badge, counts, body }
  let lastFocusModuleId = null;

  let openTabs = [];
  let activeTabId = null;
  const moduleExpanded = new Map(); // id -> boolean (details.open)
  const loadedModules = new Set(); // module ids whose contents are loaded
  const loadingModules = new Set(); // module ids currently "loading"

  let userInteractedWithGraph = false;
  let applyingGraphPose = false;
  let storedGraphPose = null;

  const graphView = createGraphView(graphLayer, {
    interaction: "map",
    renderChoiceNodes: false,
    showPhaseBands: true,
    showNodeTypeIcon: false,
    selectOnClick: false,
    limitZoomOutToFit: true,
    fitMaxZoom: 2.8,
    autoFitOnSetGraph: false,
    onNodeClick: (id) => {
      const st = runtime?.statusById?.[String(id)]?.status || "locked";
      if (st === "locked") return;
      openModuleInContent(String(id));
    },
  });

  // Mark "user interacted" only on real input events (not on initial render / programmatic fits).
  if (graphView?.svg) {
    let maybeDragStart = null;
    const DRAG_THRESHOLD_PX = 6;
    graphView.svg.addEventListener(
      "pointerdown",
      (evt) => {
        if (applyingGraphPose) return;
        maybeDragStart = { id: evt.pointerId, x: evt.clientX, y: evt.clientY };
      },
      { passive: true },
    );
    graphView.svg.addEventListener(
      "pointermove",
      (evt) => {
        if (applyingGraphPose) return;
        if (!maybeDragStart || maybeDragStart.id !== evt.pointerId) return;
        const dx = evt.clientX - maybeDragStart.x;
        const dy = evt.clientY - maybeDragStart.y;
        if (Math.hypot(dx, dy) >= DRAG_THRESHOLD_PX) {
          userInteractedWithGraph = true;
          maybeDragStart = null;
        }
      },
      { passive: true },
    );
    graphView.svg.addEventListener(
      "pointerup",
      () => {
        maybeDragStart = null;
      },
      { passive: true },
    );
    graphView.svg.addEventListener(
      "pointercancel",
      () => {
        maybeDragStart = null;
      },
      { passive: true },
    );
    graphView.svg.addEventListener(
      "wheel",
      () => {
        if (!applyingGraphPose) userInteractedWithGraph = true;
      },
      { passive: true },
    );
  }

  function computeFitPad() {
    const rect = graphShell.getBoundingClientRect();
    const base = Math.round(Math.min(rect.width, rect.height) * 0.04);
    return clampNumber(base, 18, 44);
  }

  function applyReadableZoomIfNeeded() {
    if (!graph || userInteractedWithGraph) return;

    const rect = graphShell.getBoundingClientRect();
    const vw = rect.width;
    if (!(vw > 0)) return;

    const fitK = Number(graphView.getTransform()?.k || 1);
    // Desired node width in px (node width is 200 in world units).
    const desiredNodePx = clampNumber(vw * 0.2, 150, 230);
    const desiredK = desiredNodePx / 200;

    // Avoid starting *too* zoomed-in: cap to a multiple of the "fit" zoom.
    const capK = fitK * 3.2;
    let targetK = clampNumber(Math.min(desiredK, capK), fitK, 1.85);

    // Keep phase-band corners visible horizontally at the default pose.
    const b = graphView.getWorldBounds?.() || null;
    if (b && Number.isFinite(b.w) && b.w > 0) {
      const gutter = computePanGutterPx({ width: rect.width, height: rect.height });
      const availW = Math.max(1, rect.width - gutter * 2);
      const maxKNoClipX = availW / b.w;
      targetK = Math.min(targetK, maxKNoClipX * 0.985);
    }

    if (!(targetK > fitK + 0.001)) return;

    const home = findHomeNode(graph);
    if (home) {
      const anchor = graphView.worldToClient({ x: Number(home.x || 0), y: Number(home.y || 0) });
      applyingGraphPose = true;
      graphView.zoomTo(targetK, { clientX: anchor.x, clientY: anchor.y });
      applyingGraphPose = false;
      return;
    }

    applyingGraphPose = true;
    graphView.zoomTo(targetK);
    applyingGraphPose = false;
  }

  function fitGraphSoon() {
    if (viewMode !== "overview") return;
    window.requestAnimationFrame(() => {
      const pad = computeFitPad();
      applyingGraphPose = true;
      graphView.fitToGraph(pad);
      window.requestAnimationFrame(() => {
        graphView.fitToGraph(pad);
        applyingGraphPose = false;
        applyReadableZoomIfNeeded();
      });
    });
  }

  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      if (viewMode !== "overview") return;
      // Preserve pose on resize: do not auto-fit once a pose exists.
      if (typeof graphView.setTransform === "function" && storedGraphPose) {
        applyingGraphPose = true;
        graphView.setTransform(storedGraphPose, { clampToViewport: true });
        storedGraphPose = graphView.getTransform();
        applyingGraphPose = false;
        return;
      }
      // If the user has already panned/zoomed, preserve their current pose and only re-clamp to the viewport.
      if (userInteractedWithGraph && typeof graphView.setTransform === "function") {
        applyingGraphPose = true;
        graphView.setTransform(graphView.getTransform(), { clampToViewport: true });
        storedGraphPose = graphView.getTransform();
        applyingGraphPose = false;
        return;
      }
      fitGraphSoon();
    });
    ro.observe(graphShell);
  }

  function syncWorkingSetInGraph() {
    if (!graphView?.svg) return;

    // Ensure we never show a persistent "last clicked" selection in this dummy.
    // The graph is meant as an advance organizer + working set, not a spotlight view.
    for (const el of graphView.svg.querySelectorAll(".node.is-selected")) {
      el.classList.remove("is-selected");
    }
    for (const el of graphView.svg.querySelectorAll(
      ".edge.is-related, .edge.is-in, .edge.is-out, .edge.is-in-pending, .edge.is-out-pending, .edge.is-dim",
    )) {
      el.classList.remove("is-related", "is-in", "is-out", "is-in-pending", "is-out-pending", "is-dim");
    }

    for (const el of graphView.svg.querySelectorAll(".node.is-in-working-set")) {
      el.classList.remove("is-in-working-set");
    }

    for (const id of openTabs) {
      const sel = `[data-node-id="${cssEscapeId(id)}"]`;
      const el = graphView.svg.querySelector(sel);
      if (el) el.classList.add("is-in-working-set");
    }

    // Edges: highlight only "active" arrows between opened modules
    // (this dummy keeps all arrows visually identical; the graph structure
    // itself provides the navigation/advance-organizer value).
    for (const edge of graphView.svg.querySelectorAll(".edge")) {
      edge.classList.remove("is-ws-edge", "is-ws-edge-from-done");
    }
  }

  function setView(next, { scroll } = {}) {
    const prevMode = viewMode;
    viewMode = next === "content" ? "content" : "overview";
    const isOverview = viewMode === "overview";

    if (prevMode === "overview" && !isOverview) {
      // Persist the graph pose so returning to the overview doesn't "jump" back to a tiny fit-to-graph view.
      storedGraphPose = graphView.getTransform();
    }

    document.documentElement.classList.toggle("mode-overview", isOverview);
    document.body.classList.toggle("mode-overview", isOverview);

    btnViewOverview.setAttribute("aria-pressed", isOverview ? "true" : "false");
    btnViewContent.setAttribute("aria-pressed", isOverview ? "false" : "true");
    viewOverview.hidden = !isOverview;
    viewContent.hidden = isOverview;

    window.requestAnimationFrame(() => {
      if (isOverview) {
        if (scroll !== false) viewOverview.scrollIntoView({ block: "start", inline: "nearest" });
        if (runtime) graphView.update(runtime);
        // Restore the last pose (or a readable start pose on first entry).
        if (storedGraphPose && typeof graphView.setTransform === "function") {
          applyingGraphPose = true;
          graphView.setTransform(storedGraphPose, { clampToViewport: true });
          storedGraphPose = graphView.getTransform();
          applyingGraphPose = false;
        } else {
          fitGraphSoon();
        }
        syncWorkingSetInGraph();
        return;
      }

      if (scroll !== false) {
        if (lastFocusModuleId) {
          const el = moduleEls.get(lastFocusModuleId)?.root || null;
          if (el) el.scrollIntoView({ block: "start", inline: "nearest" });
          else viewContent.scrollIntoView({ block: "start", inline: "nearest" });
        } else {
          viewContent.scrollIntoView({ block: "start", inline: "nearest" });
        }
      }
    });
  }

  function persistState() {
    ensureStateIncludesTasks(graph, state);
    writeJsonToLocalStorage(STATE_STORAGE_KEY, state);
  }

  function renderModuleHeader(node, st) {
    const id = String(node.id);
    const title = String(node.title || id);
    const rawStatus = String(st.status || "locked");
    const sl = statusLabel(rawStatus === "partial" ? "open" : rawStatus);

    const tasksLen = Array.isArray(node.tasks) ? node.tasks.length : 0;
    const mats = Array.isArray(node.materials) ? node.materials.length : 0;
    const cards = Array.isArray(node.cards) ? node.cards.length : 0;

    const done = Number(st.doneTasks || 0);
    const total = Number(st.totalTasks || 0);
    const effectiveTotal = total > 0 ? total : tasksLen;

    const badges = [];
    if (isBonusModule(node)) badges.push(`<span class="badge badge-warning">Bonus</span>`);
    badges.push(`<span class="badge ${escapeHtml(sl.badge)}">${escapeHtml(sl.label)}</span>`);
    if (runtime?.edgePrereqProgress?.[id]?.total > 1 && runtime?.edgePrereqProgress?.[id]?.required > 0) {
      const ep = runtime.edgePrereqProgress[id];
      badges.push(`<span class="badge">${escapeHtml(`${ep.done}/${ep.required}`)} frei</span>`);
    }

    const counts = [];
    if (mats > 0) counts.push(metaBadge(String(mats), "badge-meta--materials", "Materialien"));
    if (effectiveTotal > 0)
      counts.push(metaBadge(`${Math.min(done, effectiveTotal)}/${effectiveTotal}`, "badge-meta--tasks", "Aufgaben"));
    if (cards > 0) counts.push(metaBadge(String(cards), "badge-meta--cards", "Karteikarten"));

    return {
      title,
      badgesHtml: badges.join(" "),
      countsHtml: counts.join(" "),
    };
  }

  function updateModuleCards() {
    for (const node of graph.nodes || []) {
      const id = String(node.id);
      const el = moduleEls.get(id);
      if (!el) continue;

      const st = runtime.statusById?.[id] || {};
      const status = String(st.status || "locked");

      el.root.classList.toggle("is-locked", status === "locked");
      el.root.classList.toggle("is-open", status === "open");
      el.root.classList.toggle("is-partial", status === "partial");
      el.root.classList.toggle("is-done", status === "done");
      el.summary.setAttribute("aria-disabled", status === "locked" ? "true" : "false");

      const hdr = renderModuleHeader(node, st);
      el.title.textContent = hdr.title;
      el.badges.innerHTML = hdr.badgesHtml;
      el.counts.innerHTML = hdr.countsHtml;

      if (status === "locked" && el.root.open) el.root.open = false;
    }
  }

  function closeModule(id) {
    const idx = openTabs.indexOf(id);
    openTabs = openTabs.filter((x) => x !== id);
    moduleExpanded.delete(id);
    if (activeTabId === id) activeTabId = openTabs[idx] || openTabs[idx - 1] || null;
    if (lastFocusModuleId === id) lastFocusModuleId = activeTabId;
    renderOpenTabs();
    syncWorkingSetInGraph();
    renderWorkingSet();
    updateModuleCards();
  }

  function renderOpenTabs() {
    openTabsEl.innerHTML = "";

    if (!openTabs.length) {
      openTabsEl.hidden = true;
      return;
    }

    openTabsEl.hidden = false;

    for (const id of openTabs) {
      const node = nodeById(graph, id);
      if (!node) continue;
      const st = runtime?.statusById?.[String(id)]?.status || "locked";

      const tab = document.createElement("div");
      tab.className = `tab${activeTabId === id ? " is-active" : ""}`;

      const dot = document.createElement("span");
      dot.className = tabDotClass(st);
      dot.setAttribute("aria-hidden", "true");

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tab__btn";
      btn.textContent = String(node.title || id);
      btn.addEventListener("click", () => openModuleInContent(id));

      const close = document.createElement("button");
      close.type = "button";
      close.className = "tab__close";
      close.setAttribute("aria-label", `Modul schließen: ${String(node.title || id)}`);
      close.textContent = "×";
      close.addEventListener("click", (ev) => {
        ev.stopPropagation();
        closeModule(id);
      });

      tab.appendChild(dot);
      tab.appendChild(btn);
      tab.appendChild(close);
      openTabsEl.appendChild(tab);
    }
  }

  function activateModule(id) {
    if (!id) return;
    if (!openTabs.includes(id)) {
      openTabs.push(id);
      if (graph) openTabs.sort((a, b) => compareNodeIdsByGraphOrder(graph, a, b));
    }
    if (!moduleExpanded.has(id)) moduleExpanded.set(id, true);
    activeTabId = id;
    renderOpenTabs();
    syncWorkingSetInGraph();
  }

  function rerender() {
    runtime = computeRuntime(graph, state);
    graphView.update(runtime);
    updateModuleCards();
    renderOpenTabs();
    syncWorkingSetInGraph();

    for (const [id, el] of moduleEls.entries()) {
      if (!loadedModules.has(id)) continue;
      const node = nodeById(graph, id);
      if (!node) continue;
      el.body.innerHTML = buildModuleBodyHtml(runtime, state, node);
      wireTaskCheckboxes(el.body, state, () => {
        persistState();
        rerender();
      });
    }
  }

  function ensureModuleLoaded(id) {
    const el = moduleEls.get(id);
    const node = nodeById(graph, id);
    if (!el || !node) return;
    if (loadedModules.has(id)) {
      el.body.innerHTML = buildModuleBodyHtml(runtime, state, node);
      wireTaskCheckboxes(el.body, state, () => {
        persistState();
        rerender();
      });
      return;
    }
    if (loadingModules.has(id)) return;

    const st = runtime?.statusById?.[id] || {};
    if (String(st.status || "") === "locked") return;

    loadingModules.add(id);
    el.body.innerHTML = '<p class="text-muted"><small>Lade Inhalte …</small></p>';
    window.setTimeout(() => {
      loadingModules.delete(id);
      loadedModules.add(id);
      const latestEl = moduleEls.get(id);
      const latestNode = nodeById(graph, id);
      if (!latestEl || !latestNode) return;
      latestEl.body.innerHTML = buildModuleBodyHtml(runtime, state, latestNode);
      wireTaskCheckboxes(latestEl.body, state, () => {
        persistState();
        rerender();
      });
    }, 120);
  }

  function openModuleInContent(id) {
    const st = runtime?.statusById?.[id]?.status || "locked";
    if (st === "locked") return;

    const prevActive = activeTabId;
    const alreadyInSet = openTabs.includes(id);

    lastFocusModuleId = id;
    activateModule(id);
    moduleExpanded.set(id, true);

    if (!alreadyInSet || !moduleEls.has(id)) {
      renderWorkingSet();
      updateModuleCards();
    }

    const el = moduleEls.get(id);
    if (!el) return;

    if (viewMode !== "content") setView("content", { scroll: false });

    const wasOpen = el.root.open;
    el.root.open = true;
    ensureModuleLoaded(id);

    if (!(prevActive === id && viewMode === "content" && wasOpen)) {
      el.root.classList.add("is-jumped");
      el.root.scrollIntoView({ block: "start", inline: "nearest" });
      window.setTimeout(() => el.root.classList.remove("is-jumped"), 900);
    }
  }

  function renderWorkingSet() {
    contentRoot.innerHTML = "";
    moduleEls.clear();

    if (!openTabs.length) {
      const empty = document.createElement("section");
      empty.className = "surface-panel";
      empty.innerHTML = `
        <h2 class="h2" style="margin-bottom: var(--space-2);">Noch keine Module geöffnet</h2>
        <p class="text-muted">
          <small>Wechsle zur Übersicht und klicke ein freigegebenes Modul im Graphen.</small>
        </p>
        <button class="btn btn-secondary" type="button" id="btn-to-overview">Zur Übersicht</button>
      `;
      contentRoot.appendChild(empty);
      const btnToOverview = empty.querySelector("#btn-to-overview");
      if (btnToOverview) btnToOverview.addEventListener("click", () => setView("overview"));
      return;
    }

    const phases = Array.isArray(graph.phases) ? graph.phases : [];
    const phaseOrder = new Map(phases.map((p, idx) => [String(p.id || ""), idx]));

    const grouped = new Map();
    for (const id of openTabs) {
      const n = nodeById(graph, id);
      if (!n) continue;
      const pid = String(n.phaseId || "");
      if (!grouped.has(pid)) grouped.set(pid, []);
      grouped.get(pid).push(n);
    }

    const phaseIds = Array.from(grouped.keys());
    phaseIds.sort((a, b) => (phaseOrder.get(a) ?? 9999) - (phaseOrder.get(b) ?? 9999));

    function phaseTitle(pid) {
      const p = phases.find((x) => String(x.id || "") === String(pid));
      if (p && p.title) return String(p.title);
      return pid ? `Phase ${pid}` : "Ohne Phase";
    }

    for (const pid of phaseIds) {
      const nodes = grouped.get(pid) || [];
      const phaseNodes = sortNodesWithinPhase(nodes);

      const section = document.createElement("section");
      section.className = "surface-panel phase-card";
      section.setAttribute("data-phase-id", String(pid || ""));

      const header = document.createElement("div");
      header.className = "phase-header";

      const h2 = document.createElement("h2");
      h2.className = "phase-title";
      h2.textContent = phaseTitle(pid);

      const meta = document.createElement("div");
      meta.className = "phase-meta";
      meta.textContent = phaseNodes.length ? `${phaseNodes.length} Module` : "—";

      header.appendChild(h2);
      header.appendChild(meta);

      const list = document.createElement("div");
      list.className = "phase-modules";

      for (const n of phaseNodes) {
        const id = String(n.id);
        const details = document.createElement("details");
        details.className = "module-card";
        details.id = `module-${id}`;
        details.setAttribute("data-module-id", id);
        details.open = Boolean(moduleExpanded.get(id));

        const summary = document.createElement("summary");
        summary.className = "module-card__summary";

        const summaryInner = document.createElement("div");
        summaryInner.className = "module-card__summary-inner";

        const titleRow = document.createElement("div");
        titleRow.className = "module-card__title-row";

        const title = document.createElement("span");
        title.className = "module-card__title";
        title.textContent = String(n.title || id);

        const counts = document.createElement("div");
        counts.className = "module-card__counts";

        titleRow.appendChild(title);
        titleRow.appendChild(counts);

        const metaRow = document.createElement("div");
        metaRow.className = "module-card__meta";

        summaryInner.appendChild(titleRow);
        summaryInner.appendChild(metaRow);

        summary.appendChild(summaryInner);

        const body = document.createElement("div");
        body.className = "module-card__body";
        if (loadedModules.has(id)) {
          body.innerHTML = buildModuleBodyHtml(runtime, state, n);
        } else {
          body.innerHTML = '<p class="text-muted"><small>Öffne das Modul, um Inhalte zu laden.</small></p>';
        }

        details.appendChild(summary);
        details.appendChild(body);

        details.addEventListener("toggle", () => {
          const st = runtime?.statusById?.[id]?.status || "locked";
          if (details.open && st === "locked") {
            details.open = false;
            return;
          }
          if (details.open) {
            lastFocusModuleId = id;
            activateModule(id);
            moduleExpanded.set(id, true);
            ensureModuleLoaded(id);
          } else {
            moduleExpanded.set(id, false);
          }
        });

        list.appendChild(details);
        moduleEls.set(id, { root: details, summary, title, badges: metaRow, counts, body });

        if (loadedModules.has(id)) {
          wireTaskCheckboxes(body, state, () => {
            persistState();
            rerender();
          });
        } else if (details.open) {
          ensureModuleLoaded(id);
        }
      }

      section.appendChild(header);
      section.appendChild(list);
      contentRoot.appendChild(section);
    }
  }

  btnViewOverview.addEventListener("click", () => setView("overview"));
  btnViewContent.addEventListener("click", () => setView("content"));

  btnReset.addEventListener("click", () => {
    if (!graph) return;
    state = createDefaultState(graph);
    persistState();
    openTabs = [];
    activeTabId = null;
    moduleExpanded.clear();
    loadedModules.clear();
    loadingModules.clear();
    storedGraphPose = null;
    userInteractedWithGraph = false;
    renderOpenTabs();
    syncWorkingSetInGraph();
    renderWorkingSet();
    rerender();
    graphView.resetView();
  });

  (async () => {
    graph = await loadGraph({ sampleUrl: SAMPLE_URL, storageKey: GRAPH_STORAGE_KEY });
    writeJsonToLocalStorage(GRAPH_STORAGE_KEY, graph);
    unitTitleEl.textContent = String(graph?.meta?.title || "Lerneinheit");

    state = loadState(graph, { storageKey: STATE_STORAGE_KEY });
    ensureStateIncludesTasks(graph, state);
    writeJsonToLocalStorage(STATE_STORAGE_KEY, state);

    graphView.setGraph(graph);
    applyingGraphPose = true;
    graphView.fitToGraph(computeFitPad());
    applyingGraphPose = false;
    fitGraphSoon();

    renderWorkingSet();
    rerender();
    setView("overview", { scroll: false });
    syncWorkingSetInGraph();

    // Safety: apply the "readable" start zoom again once layout has fully settled
    // (helps when fonts/viewport metrics arrive late on some browsers).
    window.setTimeout(() => {
      if (viewMode === "overview") applyReadableZoomIfNeeded();
    }, 240);
  })().catch((err) => {
    graphLayer.innerHTML = `
      <div class="overlay-card" style="margin: var(--space-6);">
        <strong>Fehler</strong>
        <p class="text-muted"><small>${escapeHtml(String(err && err.message ? err.message : err))}</small></p>
      </div>
    `;
    viewContent.hidden = true;
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
