/**
 * Student Modular Workspace (UI dummy adoption)
 *
 * Why:
 * - Modular learning units are presented as a "workspace":
 *   - Overview: an advance-organizer graph (pan/zoom)
 *   - Content: a working set of opened modules (tabs + cards)
 * - This file implements the agreed dummy behavior:
 *   1A: module contents render inline in the "Inhalte" view (no right panel)
 *   2A: "Offene Module" tabs are the student's working set
 *   3A: view/tabs/pose persist via localStorage
 *
 * Security:
 * - Locked modules remain fail-closed (content is loaded via SSR fragments that
 *   return 404 for locked/missing modules).
 */

import { createGraphView } from './student_graph_view.js';

const STORAGE_PREFIX = 'gustav.learning.modular_workspace:';

function readJsonFromLocalStorage(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

function writeJsonToLocalStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    // ignore
  }
}

function clampNumber(x, lo, hi) {
  const n = Number(x);
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}

function cssEscapeId(id) {
  const raw = String(id || '');
  if (typeof CSS !== 'undefined' && CSS && typeof CSS.escape === 'function') return CSS.escape(raw);
  return raw.replace(/[^a-zA-Z0-9_-]/g, (m) => `\\${m}`);
}

function statusLabel(status) {
  const st = String(status || 'locked');
  if (st === 'done') return { label: 'fertig', badgeClass: 'badge-success' };
  if (st === 'open') return { label: 'offen', badgeClass: 'badge-primary' };
  return { label: 'gesperrt', badgeClass: '' };
}

function tabDotClass(status) {
  const st = String(status || 'locked');
  if (st === 'done') return 'tab__dot tab__dot--done';
  if (st === 'open') return 'tab__dot tab__dot--open';
  return 'tab__dot tab__dot--locked';
}

function defaultWorkspaceState() {
  return {
    view: 'overview',
    openTabs: [],
    activeTab: null,
    expanded: {},
    graphPose: null,
  };
}

function normalizeWorkspaceState(raw) {
  const st = raw && typeof raw === 'object' ? raw : {};
  const view = st.view === 'content' ? 'content' : 'overview';
  const openTabs = Array.isArray(st.openTabs) ? st.openTabs.map(String).filter(Boolean) : [];
  const activeTab = st.activeTab ? String(st.activeTab) : null;
  const expanded = st.expanded && typeof st.expanded === 'object' ? st.expanded : {};
  const graphPose = st.graphPose && typeof st.graphPose === 'object' ? st.graphPose : null;
  return { view, openTabs, activeTab, expanded, graphPose };
}

async function fetchGraph({ courseId, unitId }) {
  const url = `/api/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/graph`;
  const r = await fetch(url, { credentials: 'include', cache: 'no-store' });
  if (!r.ok) throw new Error(`graph_fetch_failed_${r.status}`);
  return await r.json();
}

function buildGraphModel(payload) {
  const unit = payload && typeof payload === 'object' ? payload.unit || {} : {};
  const phasesRaw = Array.isArray(payload?.phases) ? payload.phases : [];
  const modulesRaw = Array.isArray(payload?.modules) ? payload.modules : [];
  const edgesRaw = Array.isArray(payload?.edges) ? payload.edges : [];

  const phasesSorted = [...phasesRaw]
    .filter((p) => p && typeof p === 'object')
    .sort((a, b) => Number(a.position || 1) - Number(b.position || 1));

  const phaseIndexById = new Map(phasesSorted.map((p, idx) => [String(p.id || ''), idx]));
  const phaseTitleById = new Map(phasesSorted.map((p) => [String(p.id || ''), String(p.title || p.id || '')]));

  const BASE_X = 240;
  const BASE_Y = 140;
  const GAP_X = 260;
  const GAP_Y = 200;

  const moduleById = new Map();
  const modules = modulesRaw.filter((m) => m && typeof m === 'object');
  for (const m of modules) {
    const id = String(m.id || '');
    if (!id) continue;
    moduleById.set(id, m);
  }

  const incomingCount = new Map();
  for (const e of edgesRaw.filter((e) => e && typeof e === 'object')) {
    const to = String(e.to || '');
    if (!to) continue;
    incomingCount.set(to, Number(incomingCount.get(to) || 0) + 1);
  }

  const nodes = [];
  const runtime = {
    statusById: {},
    completedById: {},
    unlockedById: {},
    edgePrereqProgress: {},
  };

  for (const m of modules) {
    const id = String(m.id || '');
    if (!id) continue;
    const pid = String(m.phase_id || '');
    const pIdx = phaseIndexById.get(pid) ?? 0;
    const pos = Math.max(1, Number(m.position_in_phase || 1));

    const status = String(m.status || 'locked');
    const tasksDone = Math.max(0, Number(m.tasks_done || 0));
    const tasksTotal = Math.max(0, Number(m.tasks_total || 0));
    const matsCount = Math.max(0, Number(m.materials_count || 0));

    const totalIncoming = Math.max(0, Number(incomingCount.get(id) || 0));
    const prereqDone = Math.max(0, Number(m.prereq_done || 0));
    const prereqReq = Math.max(0, Number(m.prereq_required || 0));

    const x = BASE_X + (pos - 1) * GAP_X;
    const y = BASE_Y + pIdx * GAP_Y;

    nodes.push({
      id,
      type: 'module',
      title: String(m.title || id),
      phaseId: pid,
      x,
      y,
      materials: new Array(matsCount),
      cards: [],
    });

    runtime.statusById[id] = { status, doneTasks: tasksDone, totalTasks: tasksTotal };
    runtime.completedById[id] = status === 'done';
    runtime.unlockedById[id] = status === 'open' || status === 'done';
    runtime.edgePrereqProgress[id] = { total: totalIncoming, required: prereqReq, done: prereqDone };
  }

  const phases = phasesSorted.map((p) => ({ id: String(p.id || ''), title: String(p.title || p.id || '') }));
  const edges = edgesRaw
    .filter((e) => e && typeof e === 'object')
    .map((e) => ({ from: String(e.from || ''), to: String(e.to || '') }))
    .filter((e) => e.from && e.to);

  const graph = {
    meta: { title: String(unit.title || 'Lerneinheit') },
    phases,
    nodes,
    edges,
  };

  return { graph, runtime, phasesSorted, phaseTitleById, phaseIndexById, moduleById };
}

function sortModuleIdsByGraphOrder({ moduleById, phaseIndexById }, ids) {
  const uniq = Array.from(new Set((ids || []).map(String).filter(Boolean)));
  uniq.sort((aId, bId) => {
    const a = moduleById.get(String(aId)) || null;
    const b = moduleById.get(String(bId)) || null;
    if (!a && !b) return String(aId).localeCompare(String(bId), 'de');
    if (!a) return 1;
    if (!b) return -1;

    const pa = String(a.phase_id || '');
    const pb = String(b.phase_id || '');
    const ia = phaseIndexById.get(pa) ?? 9999;
    const ib = phaseIndexById.get(pb) ?? 9999;
    if (ia !== ib) return ia - ib;

    const xa = Number(a.position_in_phase || 1);
    const xb = Number(b.position_in_phase || 1);
    if (xa !== xb) return xa - xb;

    return String(aId).localeCompare(String(bId), 'de');
  });
  return uniq;
}

function initOneWorkspace(rootEl) {
  if (!rootEl || !(rootEl instanceof Element)) return;
  if (rootEl.dataset.workspaceInit === 'ready') return;
  rootEl.dataset.workspaceInit = 'ready';

  const courseId = rootEl.dataset.courseId || '';
  const unitId = rootEl.dataset.unitId || '';
  if (!courseId || !unitId) return;

  const storageKey = `${STORAGE_PREFIX}${courseId}:${unitId}`;
  let state = normalizeWorkspaceState(readJsonFromLocalStorage(storageKey) || defaultWorkspaceState());

  const graphLayer = rootEl.querySelector('#graph-layer');
  const graphShell = rootEl.querySelector('#graph-shell');
  const btnViewOverview = rootEl.querySelector('#btn-view-overview');
  const btnViewContent = rootEl.querySelector('#btn-view-content');
  const viewOverview = rootEl.querySelector('#view-overview');
  const viewContent = rootEl.querySelector('#view-content');
  const contentRoot = rootEl.querySelector('#content-root');
  const openTabsEl = rootEl.querySelector('#open-tabs');

  if (
    !graphLayer ||
    !graphShell ||
    !btnViewOverview ||
    !btnViewContent ||
    !viewOverview ||
    !viewContent ||
    !contentRoot ||
    !openTabsEl
  ) {
    return;
  }

  const graphView = createGraphView(graphLayer, {
    interaction: 'map',
    renderChoiceNodes: false,
    showPhaseBands: true,
    showNodeTypeIcon: false,
    selectOnClick: false,
    limitZoomOutToFit: true,
    autoFitOnSetGraph: false,
    onNodeClick: (id) => {
      const st = runtime?.statusById?.[String(id)]?.status || 'locked';
      if (st === 'locked') return;
      openModuleInContent(String(id));
    },
  });

  let model = null;
  let runtime = null;

  const loadedModules = new Set();
  const loadingModules = new Set();
  const moduleEls = new Map(); // module_id -> { details, body }
  const phaseEls = new Map(); // phase_id -> { section, list, meta }

  function persistState() {
    writeJsonToLocalStorage(storageKey, state);
  }

  function computeFitPad() {
    const rect = graphShell.getBoundingClientRect();
    const base = Math.round(Math.min(rect.width, rect.height) * 0.04);
    return clampNumber(base, 18, 44);
  }

  function applyGraphPoseOrFit() {
    if (!graphView || !graphView.svg) return;
    if (state.graphPose && typeof graphView.setTransform === 'function') {
      graphView.setTransform(state.graphPose, { clampToViewport: true });
      return;
    }
    graphView.fitToGraph(computeFitPad());
  }

  function setView(next, { scroll } = {}) {
    const prev = state.view;
    const viewMode = next === 'content' ? 'content' : 'overview';

    if (prev === 'overview' && viewMode !== 'overview') {
      state.graphPose = graphView.getTransform();
    }

    state.view = viewMode;
    persistState();

    const isOverview = viewMode === 'overview';
    document.documentElement.classList.toggle('mode-overview', isOverview);
    document.body.classList.toggle('mode-overview', isOverview);

    btnViewOverview.setAttribute('aria-pressed', isOverview ? 'true' : 'false');
    btnViewContent.setAttribute('aria-pressed', isOverview ? 'false' : 'true');

    viewOverview.hidden = !isOverview;
    viewContent.hidden = isOverview;

    window.requestAnimationFrame(() => {
      if (isOverview) {
        applyGraphPoseOrFit();
        if (scroll !== false) viewOverview.scrollIntoView({ block: 'start', inline: 'nearest' });
        return;
      }
      if (scroll !== false) viewContent.scrollIntoView({ block: 'start', inline: 'nearest' });
    });
  }

  function closeModule(id) {
    const mid = String(id);
    const idx = state.openTabs.indexOf(mid);
    state.openTabs = state.openTabs.filter((x) => x !== mid);
    delete state.expanded[mid];

    if (state.activeTab === mid) {
      state.activeTab = state.openTabs[idx] || state.openTabs[idx - 1] || null;
    }

    const el = moduleEls.get(mid);
    if (el && el.details && el.details.parentElement) {
      el.details.parentElement.removeChild(el.details);
    }
    moduleEls.delete(mid);

    // Remove empty phase sections.
    for (const [pid, p] of phaseEls.entries()) {
      if (!p.list.querySelector('.module-card')) {
        p.section.remove();
        phaseEls.delete(pid);
      }
    }

    persistState();
    renderOpenTabs();
    renderEmptyIfNeeded();
  }

  function renderOpenTabs() {
    openTabsEl.innerHTML = '';

    if (!state.openTabs.length) {
      openTabsEl.hidden = true;
      return;
    }

    openTabsEl.hidden = false;

    for (const id of state.openTabs) {
      const m = model?.moduleById?.get(String(id)) || null;
      if (!m) continue;
      const st = runtime?.statusById?.[String(id)]?.status || 'locked';

      const tab = document.createElement('div');
      tab.className = `tab${state.activeTab === id ? ' is-active' : ''}`;

      const dot = document.createElement('span');
      dot.className = tabDotClass(st);
      dot.setAttribute('aria-hidden', 'true');

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tab__btn';
      btn.textContent = String(m.title || id);
      btn.addEventListener('click', () => openModuleInContent(id));

      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'tab__close';
      close.setAttribute('aria-label', `Modul schließen: ${String(m.title || id)}`);
      close.textContent = '×';
      close.addEventListener('click', (ev) => {
        ev.stopPropagation();
        closeModule(id);
      });

      tab.appendChild(dot);
      tab.appendChild(btn);
      tab.appendChild(close);
      openTabsEl.appendChild(tab);
    }
  }

  function ensurePhaseSection(pid) {
    const id = String(pid || '');
    if (phaseEls.has(id)) return phaseEls.get(id);

    const section = document.createElement('section');
    section.className = 'surface-panel phase-card';
    section.setAttribute('data-phase-id', id);

    const header = document.createElement('div');
    header.className = 'phase-header';

    const h2 = document.createElement('h2');
    h2.className = 'phase-title';
    h2.textContent = model?.phaseTitleById?.get(id) || (id ? `Phase ${id}` : 'Ohne Phase');

    const meta = document.createElement('div');
    meta.className = 'phase-meta';
    meta.textContent = '—';

    header.appendChild(h2);
    header.appendChild(meta);

    const list = document.createElement('div');
    list.className = 'phase-modules';

    section.appendChild(header);
    section.appendChild(list);

    // Insert by phase order.
    const idx = model?.phaseIndexById?.get(id) ?? 9999;
    const siblings = Array.from(contentRoot.querySelectorAll('section.phase-card'));
    const insertBefore = siblings.find((sib) => {
      const sid = String(sib.getAttribute('data-phase-id') || '');
      const sidx = model?.phaseIndexById?.get(sid) ?? 9999;
      return sidx > idx;
    });
    if (insertBefore) contentRoot.insertBefore(section, insertBefore);
    else contentRoot.appendChild(section);

    phaseEls.set(id, { section, list, meta });
    return phaseEls.get(id);
  }

  function updatePhaseMeta() {
    for (const [pid, p] of phaseEls.entries()) {
      const count = p.list.querySelectorAll('.module-card').length;
      p.meta.textContent = count ? `${count} Module` : '—';
    }
  }

  function metaBadge({ label, className, title }) {
    const b = document.createElement('span');
    b.className = `badge badge-meta ${className || ''}`.trim();
    if (title) b.title = title;
    b.textContent = String(label);
    return b;
  }

  function ensureModuleCard(id) {
    const mid = String(id);
    if (moduleEls.has(mid)) return moduleEls.get(mid);

    const m = model?.moduleById?.get(mid) || null;
    if (!m) return null;
    const pid = String(m.phase_id || '');
    const phase = ensurePhaseSection(pid);
    if (!phase) return null;

    const details = document.createElement('details');
    details.className = 'module-card';
    details.id = `module-${mid}`;
    details.setAttribute('data-module-id', mid);

    const summary = document.createElement('summary');
    summary.className = 'module-card__summary';

    const summaryInner = document.createElement('div');
    summaryInner.className = 'module-card__summary-inner';

    const titleRow = document.createElement('div');
    titleRow.className = 'module-card__title-row';

    const title = document.createElement('span');
    title.className = 'module-card__title';
    title.textContent = String(m.title || mid);

    const counts = document.createElement('div');
    counts.className = 'module-card__counts';

    titleRow.appendChild(title);
    titleRow.appendChild(counts);

    const metaRow = document.createElement('div');
    metaRow.className = 'module-card__meta';

    summaryInner.appendChild(titleRow);
    summaryInner.appendChild(metaRow);
    summary.appendChild(summaryInner);

    const body = document.createElement('div');
    body.className = 'module-card__body';
    body.innerHTML = '<p class="text-muted"><small>Öffne das Modul, um Inhalte zu laden.</small></p>';

    details.appendChild(summary);
    details.appendChild(body);

    details.addEventListener('toggle', () => {
      const st = runtime?.statusById?.[mid]?.status || 'locked';
      if (details.open && st === 'locked') {
        details.open = false;
        return;
      }
      state.expanded[mid] = Boolean(details.open);
      if (details.open) {
        state.activeTab = mid;
        if (!state.openTabs.includes(mid)) state.openTabs.push(mid);
        state.openTabs = sortModuleIdsByGraphOrder(model, state.openTabs);
        persistState();
        renderOpenTabs();
        ensureModuleLoaded(mid);
      } else {
        persistState();
      }
    });

    // Insert by module order inside phase.
    const pos = Math.max(1, Number(m.position_in_phase || 1));
    const siblings = Array.from(phase.list.querySelectorAll('details.module-card'));
    const insertBefore = siblings.find((sib) => {
      const sid = String(sib.getAttribute('data-module-id') || '');
      const sm = model?.moduleById?.get(sid) || null;
      const spos = sm ? Math.max(1, Number(sm.position_in_phase || 1)) : 9999;
      return spos > pos;
    });
    if (insertBefore) phase.list.insertBefore(details, insertBefore);
    else phase.list.appendChild(details);

    moduleEls.set(mid, { details, title, metaRow, counts, body });
    return moduleEls.get(mid);
  }

  function updateModuleCards() {
    for (const [mid, el] of moduleEls.entries()) {
      const m = model?.moduleById?.get(mid) || null;
      if (!m) continue;
      const st = runtime?.statusById?.[mid] || {};
      const status = String(st.status || 'locked');

      el.details.classList.toggle('is-locked', status === 'locked');
      el.details.classList.toggle('is-open', status === 'open');
      el.details.classList.toggle('is-done', status === 'done');

      const labels = statusLabel(status);

      // Meta row: status + optional prereq progress.
      el.metaRow.innerHTML = '';
      const statusBadge = document.createElement('span');
      statusBadge.className = `badge ${labels.badgeClass}`.trim();
      statusBadge.textContent = labels.label;
      el.metaRow.appendChild(statusBadge);

      const ep = runtime?.edgePrereqProgress?.[mid] || null;
      if (ep && Number(ep.total || 0) > 1 && Number(ep.required || 0) > 0) {
        const free = document.createElement('span');
        free.className = 'badge';
        free.textContent = `${Math.min(Number(ep.done || 0), Number(ep.required || 0))}/${Math.min(Number(ep.required || 0), Number(ep.total || 0))} frei`;
        el.metaRow.appendChild(free);
      }

      // Counts: materials + tasks.
      el.counts.innerHTML = '';
      const mats = Math.max(0, Number(m.materials_count || 0));
      const totalTasks = Math.max(0, Number(m.tasks_total || 0));
      const doneTasks = Math.max(0, Number(m.tasks_done || 0));
      if (mats > 0) el.counts.appendChild(metaBadge({ label: String(mats), className: 'badge-meta--materials', title: 'Materialien' }));
      if (totalTasks > 0) {
        el.counts.appendChild(
          metaBadge({
            label: `${Math.min(doneTasks, totalTasks)}/${totalTasks}`,
            className: 'badge-meta--tasks',
            title: 'Aufgaben',
          }),
        );
      }

      // Keep locked modules collapsed.
      if (status === 'locked' && el.details.open) el.details.open = false;
    }
  }

  function ensureModuleLoaded(mid) {
    const id = String(mid);
    const el = moduleEls.get(id);
    if (!el) return;

    if (loadedModules.has(id) || loadingModules.has(id)) return;

    const st = runtime?.statusById?.[id]?.status || 'locked';
    if (st === 'locked') return;

    loadingModules.add(id);

    const placeholder = document.createElement('div');
    placeholder.className = 'module-fragment';
    placeholder.setAttribute('hx-get', `/learning/courses/${encodeURIComponent(courseId)}/units/${encodeURIComponent(unitId)}/modules/${encodeURIComponent(id)}/fragment`);
    placeholder.setAttribute('hx-trigger', 'load');
    placeholder.setAttribute('hx-target', 'this');
    placeholder.setAttribute('hx-swap', 'innerHTML');
    placeholder.innerHTML = '<p class="text-muted"><small>Lade Inhalte …</small></p>';

    const markLoaded = () => {
      loadedModules.add(id);
      loadingModules.delete(id);
      placeholder.removeAttribute('hx-get');
      placeholder.removeAttribute('hx-trigger');
      placeholder.removeAttribute('hx-target');
      placeholder.removeAttribute('hx-swap');
    };

    placeholder.addEventListener('htmx:afterSwap', markLoaded);
    placeholder.addEventListener('htmx:responseError', () => {
      loadingModules.delete(id);
    });

    el.body.innerHTML = '';
    el.body.appendChild(placeholder);

    if (window.htmx && typeof window.htmx.process === 'function') {
      window.htmx.process(placeholder);
    }
  }

  function renderEmptyIfNeeded() {
    // When no modules are open, show an empty hint card.
    if (state.openTabs.length) return;
    contentRoot.innerHTML = '';
    moduleEls.clear();
    phaseEls.clear();

    const empty = document.createElement('section');
    empty.className = 'surface-panel';
    empty.innerHTML = `
      <h2 class="h2" style="margin-bottom: var(--space-2);">Noch keine Module geöffnet</h2>
      <p class="text-muted"><small>Wechsle zur Übersicht und klicke ein freigegebenes Modul im Graphen.</small></p>
      <button class="btn btn-secondary" type="button" id="btn-to-overview">Zur Übersicht</button>
    `;
    contentRoot.appendChild(empty);
    const btn = empty.querySelector('#btn-to-overview');
    if (btn) btn.addEventListener('click', () => setView('overview'));
  }

  function openModuleInContent(id) {
    const mid = String(id);
    const st = runtime?.statusById?.[mid]?.status || 'locked';
    if (st === 'locked') return;

    if (!state.openTabs.includes(mid)) state.openTabs.push(mid);
    state.openTabs = sortModuleIdsByGraphOrder(model, state.openTabs);
    state.activeTab = mid;
    state.expanded[mid] = true;

    persistState();

    renderOpenTabs();

    // Ensure content DOM exists for this module.
    const card = ensureModuleCard(mid);
    updatePhaseMeta();
    updateModuleCards();

    // Switch view and scroll.
    if (state.view !== 'content') setView('content', { scroll: false });

    if (card && card.details) {
      card.details.open = true;
      ensureModuleLoaded(mid);

      const node = card.details;
      node.classList.add('is-jumped');
      node.scrollIntoView({ block: 'start', inline: 'nearest' });
      window.setTimeout(() => node.classList.remove('is-jumped'), 900);
    }
  }

  btnViewOverview.addEventListener('click', () => setView('overview'));
  btnViewContent.addEventListener('click', () => setView('content'));

  function restoreStateAfterGraphLoad() {
    // Prune invalid/locked modules from openTabs.
    state.openTabs = state.openTabs.filter((id) => model.moduleById.has(String(id)));
    state.openTabs = state.openTabs.filter((id) => (runtime?.statusById?.[String(id)]?.status || 'locked') !== 'locked');
    state.openTabs = sortModuleIdsByGraphOrder(model, state.openTabs);

    if (state.activeTab && !state.openTabs.includes(String(state.activeTab))) {
      state.activeTab = state.openTabs[0] || null;
    }

    // Rebuild content DOM for restored tabs (without destroying loaded content).
    contentRoot.innerHTML = '';
    moduleEls.clear();
    phaseEls.clear();

    if (!state.openTabs.length) {
      renderEmptyIfNeeded();
    } else {
      for (const id of state.openTabs) {
        const card = ensureModuleCard(id);
        if (card && state.expanded[String(id)] === true) {
          card.details.open = true;
          ensureModuleLoaded(id);
        }
      }
      updatePhaseMeta();
      updateModuleCards();
    }

    renderOpenTabs();

    // Ensure runtime is applied to the graph.
    graphView.update(runtime);

    // View restore.
    setView(state.view, { scroll: false });
  }

  (async () => {
    const payload = await fetchGraph({ courseId, unitId });
    model = buildGraphModel(payload);
    runtime = model.runtime;

    graphView.setGraph(model.graph);
    applyGraphPoseOrFit();

    restoreStateAfterGraphLoad();

    // Persist once after prune.
    persistState();
  })().catch((err) => {
    graphLayer.innerHTML = `
      <div class="overlay-card" style="margin: var(--space-6);">
        <strong>Fehler</strong>
        <p class="text-muted"><small>${String(err && err.message ? err.message : err)}</small></p>
      </div>
    `;
    viewContent.hidden = true;
  });
}

function initStudentModularWorkspace(contextEl) {
  const scope = contextEl && contextEl.querySelectorAll ? contextEl : document;
  const roots = scope.querySelectorAll('.modular-unit-page[data-unit-type="modular"]');

  // HTMX navigation swaps only the <main> contents, so global <html>/<body> classes
  // can accidentally "leak" across pages. Ensure we fail open (normal scrolling)
  // when the modular workspace is not present anymore.
  if (!document.querySelector('.modular-unit-page[data-unit-type="modular"]')) {
    document.documentElement.classList.remove('mode-overview');
    document.body.classList.remove('mode-overview');
  }

  roots.forEach((root) => initOneWorkspace(root));
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initStudentModularWorkspace(document));
} else {
  initStudentModularWorkspace(document);
}

// HTMX swaps: re-init in swapped subtree.
document.body?.addEventListener('htmx:afterSwap', (ev) => {
  const target = ev?.detail?.target;
  initStudentModularWorkspace(target || document);
});

// HTMX history restore (back/forward).
document.body?.addEventListener('htmx:restored', () => {
  initStudentModularWorkspace(document);
});
