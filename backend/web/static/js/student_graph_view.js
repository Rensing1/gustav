const SVG_NS = "http://www.w3.org/2000/svg";

// Canonical node dimensions (must match what `renderNodes()` draws).
const NODE_RECT_W = 200;
const NODE_RECT_H = 74;
const NODE_DIAMOND_W = 140;
const NODE_DIAMOND_H = 80;

// Rough node extents for view-fitting/highlighting. Kept intentionally simple.
const NODE_HALF_W = 110;
const NODE_HALF_H = 60;
const GROUP_FRAME_PAD = 70;
const PHASE_BAND_PAD_X = 80;
const PHASE_BAND_PAD_Y = 56;
const PHASE_BAND_GAP_Y = 24;

// Badge geometry (status icon on the node's corner).
// NOTE: Values are tuned for the current node shapes (rect/diamond) and styles.
const NODE_BADGE_R = 11; // 22px circle
const NODE_BADGE_RING_R = 14;
const NODE_BADGE_OVERLAP = 6; // how much the badge overlaps into the node
const NODE_BADGE_CX = NODE_BADGE_R - NODE_BADGE_OVERLAP;
const NODE_BADGE_CY = -NODE_BADGE_R + NODE_BADGE_OVERLAP;
const NODE_BADGE_RING_CIRC = 2 * Math.PI * NODE_BADGE_RING_R;
const LANE_GAP_PX = 18;
const SAME_LEVEL_EPSILON = 8;
const CURVE_FACTOR = 0.55;
const CURVE_MIN = 36;
const CURVE_MAX = 160;

function svgEl(name, attrs = {}) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    el.setAttribute(k, String(v));
  }
  return el;
}

function clamp(x, lo, hi) {
  return Math.max(lo, Math.min(hi, x));
}

function safeNum(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

function statusLabel(status) {
  const s = String(status || "");
  if (s === "done") return "fertig";
  if (s === "partial") return "teilweise";
  if (s === "open") return "offen";
  return "gesperrt";
}

function nodeIcon(type) {
  // Short, low-noise labels (kept ASCII-only).
  if (type === "required") return "P";
  if (type === "elective_required") return "WP";
  if (type === "elective") return "W";
  if (type === "flashcards") return "K";
  if (type === "choice_group") return "GR";
  return "M";
}

function nodeShape(type) {
  if (type === "choice_group") return "diamond";
  return "rect";
}

function truncateText(input, maxLen) {
  const s = String(input || "");
  const n = Math.max(0, Number(maxLen || 0));
  if (!n) return "";
  if (s.length <= n) return s;
  if (n <= 3) return s.slice(0, n);
  return `${s.slice(0, n - 3)}...`;
}

function buildMiniIcon(kind) {
  // Small pictograms for "materials / tasks / cards" that work in pure SVG.
  // Uses CSS variables via presentation attributes (supported in modern browsers).
  const g = svgEl("g", { class: `node-meta-icon node-meta-icon--${kind}` });
  const stroke = "var(--color-text-muted)";
  const sw = "2";

  if (kind === "tasks") {
    g.appendChild(svgEl("rect", { x: 0, y: -10, width: 12, height: 12, rx: 3, ry: 3, fill: "none", stroke, "stroke-width": sw }));
    return g;
  }
  if (kind === "materials") {
    g.appendChild(svgEl("rect", { x: 0, y: -11, width: 12, height: 14, rx: 2, ry: 2, fill: "none", stroke, "stroke-width": sw }));
    g.appendChild(svgEl("path", { d: "M 3 -6 H 10", fill: "none", stroke, "stroke-width": sw, "stroke-linecap": "round" }));
    g.appendChild(svgEl("path", { d: "M 3 -2 H 8", fill: "none", stroke, "stroke-width": sw, "stroke-linecap": "round" }));
    return g;
  }
  if (kind === "cards") {
    g.appendChild(svgEl("rect", { x: 2, y: -9, width: 12, height: 10, rx: 2, ry: 2, fill: "none", stroke, "stroke-width": sw }));
    g.appendChild(svgEl("rect", { x: 0, y: -11, width: 12, height: 10, rx: 2, ry: 2, fill: "none", stroke, "stroke-width": sw, opacity: "0.7" }));
    return g;
  }

  g.appendChild(svgEl("rect", { x: 0, y: -10, width: 12, height: 12, rx: 3, ry: 3, fill: "none", stroke, "stroke-width": sw }));
  return g;
}

function intersectRectBoundary(center, dx, dy, halfW, halfH) {
  if (!(halfW > 0) || !(halfH > 0)) return { x: center.x, y: center.y };
  if (!(dx || dy)) return { x: center.x, y: center.y };
  const tx = dx === 0 ? Infinity : halfW / Math.abs(dx);
  const ty = dy === 0 ? Infinity : halfH / Math.abs(dy);
  const t = Math.min(tx, ty);
  return { x: center.x + dx * t, y: center.y + dy * t };
}

function intersectDiamondBoundary(center, dx, dy, halfW, halfH) {
  if (!(halfW > 0) || !(halfH > 0)) return { x: center.x, y: center.y };
  if (!(dx || dy)) return { x: center.x, y: center.y };
  const denom = Math.abs(dx) / halfW + Math.abs(dy) / halfH;
  if (!(denom > 0)) return { x: center.x, y: center.y };
  const t = 1 / denom;
  return { x: center.x + dx * t, y: center.y + dy * t };
}

function edgeEndpointAtNode(node, towardNode) {
  const center = { x: safeNum(node?.x), y: safeNum(node?.y) };
  const dx = safeNum(towardNode?.x) - center.x;
  const dy = safeNum(towardNode?.y) - center.y;
  const shape = nodeShape(String(node?.type || ""));

  if (shape === "diamond") {
    return intersectDiamondBoundary(center, dx, dy, NODE_DIAMOND_W / 2, NODE_DIAMOND_H / 2);
  }
  return intersectRectBoundary(center, dx, dy, NODE_RECT_W / 2, NODE_RECT_H / 2);
}

function edgeEndpoints(a, b) {
  const p1 = edgeEndpointAtNode(a, b);
  const p2 = edgeEndpointAtNode(b, a);
  return { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y };
}

function laneOffsetForIndex(index, count, gap) {
  const i = Number(index || 0);
  const size = Math.max(0, Number(count || 0));
  const g = Number(gap || 0);
  if (!(size > 1) || !(g > 0)) return 0;
  const mid = (size - 1) / 2;
  return (i - mid) * g;
}

function isSameLevel(a, b) {
  return Math.abs(safeNum(a?.y) - safeNum(b?.y)) < SAME_LEVEL_EPSILON;
}

function collectRenderableEdges(edges, nodeById) {
  const expanded = [];
  for (const e of edges || []) {
    const fromId = String(e?.from || "");
    const toId = String(e?.to || "");
    const a = nodeById.get(fromId);
    const b = nodeById.get(toId);
    if (!a || !b) continue;
    const samePhase = String(a.phaseId || "") && String(a.phaseId || "") === String(b.phaseId || "");
    const sameLevel = isSameLevel(a, b);
    expanded.push({ fromId, toId, a, b, samePhase, sameLevel });
  }
  return expanded;
}

function buildLaneGroups(expanded) {
  const grouped = new Map();
  const stackedOutCount = new Map();
  const stackedInCount = new Map();

  for (const ed of expanded || []) {
    if (!(ed.samePhase === true) || ed.sameLevel === true) continue;
    stackedOutCount.set(ed.fromId, Number(stackedOutCount.get(ed.fromId) || 0) + 1);
    stackedInCount.set(ed.toId, Number(stackedInCount.get(ed.toId) || 0) + 1);
  }

  for (const ed of expanded || []) {
    const samePhase = ed.samePhase === true;
    let key = "";
    if (samePhase) {
      if (ed.sameLevel === true) {
        key = `same:${String(ed.a?.phaseId || "")}:flat:${String(ed.fromId || "")}`;
      } else {
        const outC = Number(stackedOutCount.get(ed.fromId) || 0);
        const inC = Number(stackedInCount.get(ed.toId) || 0);
        const anchor = outC >= inC ? `from:${String(ed.fromId || "")}` : `to:${String(ed.toId || "")}`;
        key = `same:${String(ed.a?.phaseId || "")}:stack:${anchor}`;
      }
    } else {
      key = `cross:${String(ed.a?.phaseId || "")}>${String(ed.b?.phaseId || "")}:from:${String(ed.fromId || "")}`;
    }
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(ed);
  }
  return grouped;
}

function sortEdgesDeterministically(list) {
  if (!Array.isArray(list)) return;
  list.sort((x, y) => {
    const xay = safeNum(x.a?.y);
    const yay = safeNum(y.a?.y);
    if (xay !== yay) return xay - yay;
    const xax = safeNum(x.a?.x);
    const yax = safeNum(y.a?.x);
    if (xax !== yax) return xax - yax;
    const xby = safeNum(x.b?.y);
    const yby = safeNum(y.b?.y);
    if (xby !== yby) return xby - yby;
    const xbx = safeNum(x.b?.x);
    const ybx = safeNum(y.b?.x);
    if (xbx !== ybx) return xbx - ybx;
    const fromCmp = String(x.fromId || "").localeCompare(String(y.fromId || ""));
    if (fromCmp !== 0) return fromCmp;
    return String(x.toId || "").localeCompare(String(y.toId || ""));
  });
}

function computeLaneOffsets(ed, lane) {
  const samePhase = ed?.samePhase === true;
  const sameLevel = ed?.sameLevel === true;
  let offsetX = 0;
  let offsetY = 0;

  if (samePhase) {
    // Same phase: horizontal edges separate vertically.
    // Stacked edges (top->bottom) separate horizontally.
    if (sameLevel) offsetY = lane;
    else offsetX = lane;
  } else {
    // Cross phase edges separate in x to keep lanes visible.
    offsetX = lane;
  }
  return { offsetX, offsetY };
}

function buildEdgePath(endpoints, offsets) {
  const x1 = safeNum(endpoints?.x1);
  const y1 = safeNum(endpoints?.y1);
  const x2 = safeNum(endpoints?.x2);
  const y2 = safeNum(endpoints?.y2);
  const offsetX = safeNum(offsets?.offsetX);
  const offsetY = safeNum(offsets?.offsetY);

  const dx = x2 - x1;
  const dy = y2 - y1;
  const adx = Math.abs(dx);
  const ady = Math.abs(dy);
  let d = `M ${x1} ${y1} L ${x2} ${y2}`;
  if (adx > 8 || ady > 8) {
    if (ady >= adx) {
      const c = clamp(ady * CURVE_FACTOR, CURVE_MIN, CURVE_MAX) * Math.sign(dy || 1);
      d = `M ${x1} ${y1} C ${x1 + offsetX} ${y1 + c + offsetY} ${x2 + offsetX} ${y2 - c + offsetY} ${x2} ${y2}`;
    } else {
      const c = clamp(adx * CURVE_FACTOR, CURVE_MIN, CURVE_MAX) * Math.sign(dx || 1);
      d = `M ${x1} ${y1} C ${x1 + c + offsetX} ${y1 + offsetY} ${x2 - c + offsetX} ${y2 + offsetY} ${x2} ${y2}`;
    }
  }
  return d;
}

export function createGraphView(container, opts = {}) {
  const onNodeClick = typeof opts.onNodeClick === "function" ? opts.onNodeClick : () => {};
  const onTransformChange =
    typeof opts.onTransformChange === "function" ? opts.onTransformChange : () => {};
  const onNodePositionChange =
    typeof opts.onNodePositionChange === "function" ? opts.onNodePositionChange : null;
  const renderChoiceNodes = opts.renderChoiceNodes !== false;
  const showNodeTypeIcon = opts.showNodeTypeIcon !== false;
  let showPhaseBands = opts.showPhaseBands === true;
  const interaction = String(opts.interaction || "").toLowerCase() === "scroll" ? "scroll" : "map";
  const limitZoomOutToFit = opts.limitZoomOutToFit === true;
  const constrainPan = opts.constrainPan !== false;
  const autoFitOnSetGraph = opts.autoFitOnSetGraph !== false;
  const selectOnClick = opts.selectOnClick !== false;
  const fitMaxZoom = Number(opts.fitMaxZoom);
  const maxFitZoom = Number.isFinite(fitMaxZoom) && fitMaxZoom > 0 ? fitMaxZoom : 1.4;

  const svg = svgEl("svg", {
    class: interaction === "scroll" ? "graph-svg graph-svg--scroll" : "graph-svg",
    role: "img",
    "aria-label": "Modul-Graph",
    width: "100%",
    height: "100%",
  });
  const defs = svgEl("defs");
  const marker = svgEl("marker", {
    id: "arrow",
    viewBox: "0 0 10 10",
    refX: "10",
    refY: "5",
    markerWidth: "9",
    markerHeight: "9",
    orient: "auto-start-reverse",
  });
  marker.appendChild(svgEl("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "edge-arrow", fill: "context-stroke" }));
  defs.appendChild(marker);
  svg.appendChild(defs);

  const stage = svgEl("g", { class: "graph-stage" });
  const bandsGroup = svgEl("g", { class: "graph-bands" });
  const framesGroup = svgEl("g", { class: "graph-frames" });
  const edgesGroup = svgEl("g", { class: "graph-edges" });
  const nodesGroup = svgEl("g", { class: "graph-nodes" });
  stage.appendChild(bandsGroup);
  stage.appendChild(framesGroup);
  stage.appendChild(edgesGroup);
  stage.appendChild(nodesGroup);
  svg.appendChild(stage);

  container.appendChild(svg);

  let graph = null;
  let nodeById = new Map();
  let nodeElById = new Map();
  let edgeEls = [];
  let groupFrameById = new Map(); // groupId -> { rect, label }
  let selectedId = null;
  let lastRuntime = null;

  let tx = 0;
  let ty = 0;
  let k = 1;

  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 3.0;
  let minZoom = MIN_ZOOM;
  let cachedWorldBounds = null;

  function getWorldBounds() {
    if (cachedWorldBounds) return cachedWorldBounds;
    cachedWorldBounds = computeWorldBounds();
    return cachedWorldBounds;
  }

  function refreshWorldBounds() {
    cachedWorldBounds = computeWorldBounds();
    return cachedWorldBounds;
  }

  function clampTransform(next = null, viewportRect = null) {
    if (next && typeof next === "object") {
      tx = safeNum(next.tx);
      ty = safeNum(next.ty);
    }
    if (interaction !== "map") return;
    if (!constrainPan) return;
    if (!graph) return;

    const rect = viewportRect || svg.getBoundingClientRect();
    const vw = rect.width;
    const vh = rect.height;
    if (!(vw > 0) || !(vh > 0)) return;

    const b = getWorldBounds();

    // Keep a responsive gutter so the graph can't be "wiped away" completely.
    const basePad = Math.round(Math.min(vw, vh) * 0.08);
    const pad = clamp(basePad, 24, 96);

    const bw = Math.max(1, b.w) * k;
    if (bw <= vw - pad * 2) {
      // Graph fits: keep it fully visible within padding.
      const lo = pad - b.minX * k;
      const hi = (vw - pad) - b.maxX * k;
      tx = clamp(tx, lo, hi);
    } else {
      // Graph larger than viewport: keep both sides reachable, but never fully off-screen.
      const lo = (vw - pad) - b.maxX * k;
      const hi = pad - b.minX * k;
      tx = clamp(tx, lo, hi);
    }

    const bh = Math.max(1, b.h) * k;
    if (bh <= vh - pad * 2) {
      const lo = pad - b.minY * k;
      const hi = (vh - pad) - b.maxY * k;
      ty = clamp(ty, lo, hi);
    } else {
      const lo = (vh - pad) - b.maxY * k;
      const hi = pad - b.minY * k;
      ty = clamp(ty, lo, hi);
    }
  }

  function applyTransform() {
    stage.setAttribute("transform", `translate(${tx},${ty}) scale(${k})`);
    onTransformChange({ tx, ty, k });
  }

  let transformRaf = null;
  function scheduleTransform() {
    if (transformRaf) return;
    transformRaf = requestAnimationFrame(() => {
      transformRaf = null;
      applyTransform();
    });
  }

  let interactionTimer = null;
  function startInteracting(timeoutMs = 0) {
    svg.classList.add("is-interacting");
    if (interactionTimer) window.clearTimeout(interactionTimer);
    interactionTimer = null;
    if (timeoutMs > 0) {
      interactionTimer = window.setTimeout(() => {
        svg.classList.remove("is-interacting");
        interactionTimer = null;
      }, timeoutMs);
    }
  }

  function stopInteracting() {
    if (interactionTimer) window.clearTimeout(interactionTimer);
    interactionTimer = null;
    svg.classList.remove("is-interacting");
  }

  function computeWorldBounds() {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    function includeBox(x0, y0, x1, y1) {
      minX = Math.min(minX, x0);
      minY = Math.min(minY, y0);
      maxX = Math.max(maxX, x1);
      maxY = Math.max(maxY, y1);
    }

    if (!graph) {
      return { minX: 0, minY: 0, maxX: 1, maxY: 1, w: 1, h: 1, cx: 0.5, cy: 0.5 };
    }

    for (const n of graph.nodes || []) {
      const type = String(n.type || "");
      if (!renderChoiceNodes && type === "choice_group") continue;
      const x = safeNum(n.x);
      const y = safeNum(n.y);
      includeBox(x - NODE_HALF_W, y - NODE_HALF_H, x + NODE_HALF_W, y + NODE_HALF_H);
    }

    // Include choice-group frames even if the group node itself is hidden.
    for (const n of graph.nodes || []) {
      if (String(n.type) !== "choice_group") continue;
      const choice = n.choice || {};
      const memberIds = Array.isArray(choice.memberIds) ? choice.memberIds.map(String) : [];
      const members = memberIds.map((id) => nodeById.get(id)).filter(Boolean);
      if (!members.length) continue;

      let mMinX = Infinity;
      let mMinY = Infinity;
      let mMaxX = -Infinity;
      let mMaxY = -Infinity;
      for (const m of members) {
        const x = safeNum(m.x);
        const y = safeNum(m.y);
        mMinX = Math.min(mMinX, x - NODE_HALF_W);
        mMinY = Math.min(mMinY, y - NODE_HALF_H);
        mMaxX = Math.max(mMaxX, x + NODE_HALF_W);
        mMaxY = Math.max(mMaxY, y + NODE_HALF_H);
      }
      includeBox(mMinX - GROUP_FRAME_PAD, mMinY - GROUP_FRAME_PAD, mMaxX + GROUP_FRAME_PAD, mMaxY + GROUP_FRAME_PAD);
    }

    // Phase "bands" extend beyond node extents. Include their padding so panning/fit
    // doesn't clip the rounded "card" edges (common source of "can't reach the edges"
    // reports when zoomed).
    const phases = Array.isArray(graph.phases) ? graph.phases : [];
    if (showPhaseBands === true && phases.length) {
      if (Number.isFinite(minX) && Number.isFinite(minY) && Number.isFinite(maxX) && Number.isFinite(maxY)) {
        includeBox(
          minX - PHASE_BAND_PAD_X,
          minY - PHASE_BAND_PAD_Y,
          maxX + PHASE_BAND_PAD_X,
          maxY + PHASE_BAND_PAD_Y,
        );
      }
    }

    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
      return { minX: 0, minY: 0, maxX: 1, maxY: 1, w: 1, h: 1, cx: 0.5, cy: 0.5 };
    }

    const w = Math.max(1, maxX - minX);
    const h = Math.max(1, maxY - minY);
    return { minX, minY, maxX, maxY, w, h, cx: minX + w / 2, cy: minY + h / 2 };
  }

  function fitToGraph(pad = 64) {
    if (interaction === "scroll") {
      if (!graph) return false;
      const b = getWorldBounds();
      const safePad = Math.max(0, Number(pad || 0));
      const w = Math.max(1, b.w + safePad * 2);
      const h = Math.max(1, b.h + safePad * 2);
      svg.setAttribute("width", String(Math.round(w)));
      svg.setAttribute("height", String(Math.round(h)));
      k = 1;
      tx = -(b.minX - safePad);
      ty = -(b.minY - safePad);
      applyTransform();
      return true;
    }

    if (!graph) return false;
    const rect = svg.getBoundingClientRect();
    const vw = rect.width;
    const vh = rect.height;
    if (!(vw > 0) || !(vh > 0)) return false;

    const b = getWorldBounds();
    // Avoid pathological tiny scales when the element is still at the browser's
    // default SVG size (e.g. 300×150) before CSS/layout settles.
    const maxPad = Math.round(Math.min(vw, vh) * 0.12);
    const safePad = clamp(Number(pad || 0), 0, maxPad);
    const availW = Math.max(1, vw - safePad * 2);
    const availH = Math.max(1, vh - safePad * 2);
    const nextK = clamp(Math.min(availW / b.w, availH / b.h), MIN_ZOOM, Math.min(MAX_ZOOM, maxFitZoom));

    k = nextK;
    minZoom = limitZoomOutToFit ? nextK : MIN_ZOOM;
    tx = (vw / 2) - b.cx * k;
    ty = (vh / 2) - b.cy * k;
    applyTransform();
    return true;
  }

  function resetView() {
    if (graph) {
      fitToGraph();
      return;
    }
    tx = 0;
    ty = 0;
    k = 1;
    applyTransform();
  }

  function worldToClient(pt, viewportRect = null) {
    const rect = viewportRect || svg.getBoundingClientRect();
    return {
      x: rect.left + tx + pt.x * k,
      y: rect.top + ty + pt.y * k,
    };
  }

  function clientToWorld(pt, viewportRect = null) {
    const rect = viewportRect || svg.getBoundingClientRect();
    return {
      x: (pt.x - rect.left - tx) / k,
      y: (pt.y - rect.top - ty) / k,
    };
  }

  function clearSvgChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function renderBands() {
    clearSvgChildren(bandsGroup);
    if (!graph || showPhaseBands !== true) return;
    const phases = Array.isArray(graph.phases) ? graph.phases : [];
    if (!phases.length) return;

    // Global extents (x) so bands read as "horizontal stripes".
    let minX = Infinity;
    let maxX = -Infinity;
    for (const n of graph.nodes || []) {
      const type = String(n.type || "");
      if (!renderChoiceNodes && type === "choice_group") continue;
      const x = safeNum(n.x);
      minX = Math.min(minX, x - NODE_HALF_W);
      maxX = Math.max(maxX, x + NODE_HALF_W);
    }
    if (!Number.isFinite(minX) || !Number.isFinite(maxX)) return;

    const x = minX - PHASE_BAND_PAD_X;
    const w = (maxX - minX) + PHASE_BAND_PAD_X * 2;

    const phaseItems = [];
    for (const p of phases) {
      const pid = String(p.id || "");
      if (!pid) continue;
      const title = String(p.title || pid);

      const nodesInPhase = (graph.nodes || []).filter((n) => {
        const type = String(n.type || "");
        if (!renderChoiceNodes && type === "choice_group") return false;
        if (type === "flashcards") return false; // flashcards are cross-cutting; keep bands about phases, not drills
        return String(n.phaseId || "") === pid;
      });
      if (!nodesInPhase.length) continue;

      let minY = Infinity;
      let maxY = -Infinity;
      for (const n of nodesInPhase) {
        const y = safeNum(n.y);
        minY = Math.min(minY, y - NODE_HALF_H);
        maxY = Math.max(maxY, y + NODE_HALF_H);
      }
      if (!Number.isFinite(minY) || !Number.isFinite(maxY)) continue;

      phaseItems.push({
        id: pid,
        title,
        minY,
        maxY,
        topPad: PHASE_BAND_PAD_Y,
        bottomPad: PHASE_BAND_PAD_Y,
      });
    }
    if (!phaseItems.length) return;

    // Sort by vertical position so we can enforce a consistent gap between "cards".
    phaseItems.sort((a, b) => a.minY - b.minY);

    for (let i = 0; i < phaseItems.length - 1; i += 1) {
      const cur = phaseItems[i];
      const next = phaseItems[i + 1];
      const available = next.minY - cur.maxY;
      const effectiveGap = Math.max(0, Math.min(PHASE_BAND_GAP_Y, available));
      const paddingTotal = Math.max(0, available - effectiveGap);
      const share = paddingTotal / 2;
      cur.bottomPad = Math.min(cur.bottomPad, share);
      next.topPad = Math.min(next.topPad, share);
    }

    for (const it of phaseItems) {
      const y0 = it.minY - it.topPad;
      const y1 = it.maxY + it.bottomPad;
      const y = y0;
      const h = Math.max(1, y1 - y0);

      const rect = svgEl("rect", {
        x,
        y,
        width: w,
        height: h,
        rx: 22,
        ry: 22,
        class: "phase-band",
        "data-phase-id": it.id,
      });
      bandsGroup.appendChild(rect);

      const label = svgEl("text", {
        x: x + 18,
        y: y + 28,
        class: "phase-label",
        "data-phase-id": it.id,
      });
      label.textContent = it.title;
      bandsGroup.appendChild(label);
    }
  }

  function renderFrames() {
    clearSvgChildren(framesGroup);
    groupFrameById = new Map();
    if (!graph) return;

    for (const n of graph.nodes || []) {
      if (String(n.type) !== "choice_group") continue;
      const choice = n.choice || {};
      const memberIds = Array.isArray(choice.memberIds) ? choice.memberIds.map(String) : [];
      const members = memberIds.map((id) => nodeById.get(id)).filter(Boolean);
      if (!members.length) continue;

      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      for (const m of members) {
        minX = Math.min(minX, Number(m.x || 0));
        minY = Math.min(minY, Number(m.y || 0));
        maxX = Math.max(maxX, Number(m.x || 0));
        maxY = Math.max(maxY, Number(m.y || 0));
      }
      const pad = 70;
      const x = minX - pad;
      const y = minY - pad;
      const w = (maxX - minX) + pad * 2;
      const h = (maxY - minY) + pad * 2;

      const rect = svgEl("rect", {
        x,
        y,
        width: w,
        height: h,
        rx: 18,
        ry: 18,
        class: "group-frame",
        "data-group-id": String(n.id),
        tabindex: "0",
        role: "button",
        "aria-label": `Wahlpflicht: ${String(n.title || n.id)}`,
      });
      framesGroup.appendChild(rect);

      // Group label: updated later in `update(runtime)` (needs progress).
      const label = svgEl("text", {
        x: x + 16,
        y: y + 22,
        class: "group-label",
        "data-group-id": String(n.id),
      });
      label.textContent = "Wahlpflicht";
      framesGroup.appendChild(label);

      const gid = String(n.id);
      groupFrameById.set(gid, { rect, label });

      // Allow selecting the group even when the group node itself is hidden.
      rect.addEventListener("click", (evt) => {
        evt.stopPropagation();
        selectNode(gid);
        onNodeClick(gid, evt);
      });
      rect.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter" || evt.key === " ") {
          evt.preventDefault();
          selectNode(gid);
          onNodeClick(gid, evt);
        }
      });
    }
  }

  function _addEdge(out, seen, fromId, toId) {
    const f = String(fromId || "");
    const t = String(toId || "");
    if (!f || !t) return;
    if (!nodeById.get(f) || !nodeById.get(t)) return;
    const key = `${f}::${t}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ from: f, to: t });
  }

  function computeVisibleEdges() {
    const raw = Array.isArray(graph?.edges) ? graph.edges : [];
    const out = [];
    const seen = new Set();

    if (renderChoiceNodes) {
      for (const e of raw) _addEdge(out, seen, e.from, e.to);
      return out;
    }

    const groupNodes = (graph.nodes || []).filter((n) => String(n.type) === "choice_group");
    const groupIds = new Set(groupNodes.map((n) => String(n.id)));

    // Keep edges that do not involve group nodes.
    for (const e of raw) {
      const fromId = String(e.from || "");
      const toId = String(e.to || "");
      if (!fromId || !toId) continue;
      if (groupIds.has(fromId) || groupIds.has(toId)) continue;
      _addEdge(out, seen, fromId, toId);
    }

    // Expand group nodes into "branch + join" edges to avoid extra diamond nodes.
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
        for (const m of members) _addEdge(out, seen, s, m);
      }
      for (const m of members) {
        for (const t of targets) _addEdge(out, seen, m, t);
      }
    }

    return out;
  }

  function renderEdges() {
    clearSvgChildren(edgesGroup);
    edgeEls = [];
    if (!graph) return;

    const edges = computeVisibleEdges();
    const expanded = collectRenderableEdges(edges, nodeById);
    const grouped = buildLaneGroups(expanded);
    const LANE_GAP = LANE_GAP_PX;
    for (const list of grouped.values()) {
      sortEdgesDeterministically(list);

      list.forEach((ed, idx) => {
        const lane = laneOffsetForIndex(idx, list.length, LANE_GAP);
        const offsets = computeLaneOffsets(ed, lane);
        const endpoints = edgeEndpoints(ed.a, ed.b);
        const d = buildEdgePath(endpoints, offsets);
        const path = svgEl("path", {
          d,
          class: "edge",
          "data-from": ed.fromId,
          "data-to": ed.toId,
          "marker-end": "url(#arrow)",
        });
        edgesGroup.appendChild(path);
        edgeEls.push({ el: path, from: ed.fromId, to: ed.toId });
      });
    }
  }

  function renderNodes() {
    clearSvgChildren(nodesGroup);
    nodeElById = new Map();
    if (!graph) return;

    for (const n of graph.nodes || []) {
      const id = String(n.id);
      const type = String(n.type || "module");
      if (!renderChoiceNodes && type === "choice_group") continue;
      const x = Number(n.x || 0);
      const y = Number(n.y || 0);

      const g = svgEl("g", {
        class: `node node--${type}`,
        "data-node-id": id,
        transform: `translate(${x},${y})`,
        tabindex: "0",
        role: "button",
        "aria-label": String(n.title || id),
      });

      const tooltip = svgEl("title");
      tooltip.textContent = String(n.title || id);
      g.appendChild(tooltip);

      const shape = nodeShape(type);
      if (shape === "diamond") {
        const w = NODE_DIAMOND_W;
        const h = NODE_DIAMOND_H;
        const d = `M 0 ${-h / 2} L ${w / 2} 0 L 0 ${h / 2} L ${-w / 2} 0 Z`;
        g.appendChild(svgEl("path", { d, class: "node-shape" }));
      } else {
        const w = NODE_RECT_W;
        const h = NODE_RECT_H;
        g.appendChild(
          svgEl("rect", { x: -w / 2, y: -h / 2, width: w, height: h, rx: 16, ry: 16, class: "node-shape" })
        );
      }

      const leftX = showNodeTypeIcon ? -62 : -88;
      const title = svgEl("text", { class: "node-title", x: leftX, y: -10 });
      title.textContent = truncateText(String(n.title || id), 26);
      const iconW = shape === "diamond" ? NODE_DIAMOND_W : NODE_RECT_W;
      const iconH = shape === "diamond" ? NODE_DIAMOND_H : NODE_RECT_H;
      // Badge sits on the node's top-right edge (straddles the border slightly),
      // so it never overlays title/meta content.
      const badge = svgEl("g", { class: "node-badge", transform: `translate(${iconW / 2},${-iconH / 2})`, "aria-hidden": "true" });
      badge.setAttribute("display", "none");

      const badgeRing = svgEl("g", { class: "node-badge-ring" });
      badgeRing.setAttribute("display", "none");
      const badgeRingTrack = svgEl("circle", {
        class: "node-badge-ring-track",
        cx: NODE_BADGE_CX,
        cy: NODE_BADGE_CY,
        r: NODE_BADGE_RING_R,
      });
      const badgeRingProgress = svgEl("circle", {
        class: "node-badge-ring-progress",
        cx: NODE_BADGE_CX,
        cy: NODE_BADGE_CY,
        r: NODE_BADGE_RING_R,
        transform: `rotate(-90 ${NODE_BADGE_CX} ${NODE_BADGE_CY})`,
        "stroke-dasharray": String(NODE_BADGE_RING_CIRC),
        "stroke-dashoffset": String(NODE_BADGE_RING_CIRC),
      });
      badgeRing.appendChild(badgeRingTrack);
      badgeRing.appendChild(badgeRingProgress);

      const badgeBg = svgEl("circle", { class: "node-badge-bg", cx: NODE_BADGE_CX, cy: NODE_BADGE_CY, r: NODE_BADGE_R });
      const badgeIcon = svgEl("g", { class: "node-badge-icon", transform: `translate(${NODE_BADGE_CX},${NODE_BADGE_CY})` });
      const badgeLock = svgEl("g", { class: "node-badge-icon--lock" });
      badgeLock.setAttribute("display", "none");
      // Lock is visually "bottom heavy" → shift up and scale slightly for the compact badge.
      badgeLock.setAttribute("transform", "translate(0,-2.0) scale(0.78)");
      badgeLock.appendChild(
        svgEl("rect", { class: "node-status-lock-body", x: -6, y: -1, width: 12, height: 10, rx: 2, ry: 2 })
      );
      badgeLock.appendChild(
        svgEl("path", { class: "node-status-lock-shackle", d: "M -4 -1 V -4 A 4 4 0 0 1 4 -4 V -1" })
      );
      const badgeDone = svgEl("path", { class: "node-status-icon--done", d: "M -5 0 L -2 4 L 6 -4" });
      badgeDone.setAttribute("display", "none");
      badgeIcon.appendChild(badgeLock);
      badgeIcon.appendChild(badgeDone);

      // Render order matters: ring first (so the badge fill hides the inner half of the ring).
      badge.appendChild(badgeRing);
      badge.appendChild(badgeBg);
      badge.appendChild(badgeIcon);
      const sub = svgEl("text", { class: "node-sub", x: leftX, y: 14 });
      sub.textContent = "";
      const meta = svgEl("g", { class: "node-meta", transform: `translate(${leftX},20)` });
      const tasksItem = svgEl("g", { class: "node-meta-item node-meta-item--tasks", transform: "translate(0,0)" });
      tasksItem.appendChild(buildMiniIcon("tasks"));
      const tasksCount = svgEl("text", { class: "node-sub", x: 18, y: 0 });
      tasksItem.appendChild(tasksCount);
      const matsItem = svgEl("g", { class: "node-meta-item node-meta-item--materials", transform: "translate(78,0)" });
      matsItem.appendChild(buildMiniIcon("materials"));
      const matsCount = svgEl("text", { class: "node-sub", x: 18, y: 0 });
      matsItem.appendChild(matsCount);
      const cardsItem = svgEl("g", { class: "node-meta-item node-meta-item--cards", transform: "translate(140,0)" });
      cardsItem.appendChild(buildMiniIcon("cards"));
      const cardsCount = svgEl("text", { class: "node-sub", x: 18, y: 0 });
      cardsItem.appendChild(cardsCount);
      meta.appendChild(tasksItem);
      meta.appendChild(matsItem);
      meta.appendChild(cardsItem);
      meta.setAttribute("display", "none");
      if (showNodeTypeIcon) {
        const icon = svgEl("text", { class: "node-icon", x: -88, y: -10 });
        icon.textContent = nodeIcon(type);
        g.appendChild(icon);
      }
      g.appendChild(title);
      g.appendChild(badge);
      g.appendChild(sub);
      g.appendChild(meta);

      g.addEventListener("click", (evt) => {
        evt.stopPropagation();
        if (interaction === "map" && performance.now() < suppressClickUntil) return;
        if (selectOnClick) selectNode(id);
        onNodeClick(id, evt);
      });
      g.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter" || evt.key === " ") {
          evt.preventDefault();
          if (selectOnClick) selectNode(id);
          onNodeClick(id, evt);
        }
      });

      nodesGroup.appendChild(g);
      nodeElById.set(id, {
        root: g,
        tooltip,
        title,
        badge,
        badgeRing,
        badgeRingTrack,
        badgeRingProgress,
        badgeBg,
        badgeIcon,
        badgeLock,
        badgeDone,
        sub,
        meta,
        metaTasksItem: tasksItem,
        metaTasksCount: tasksCount,
        metaMatsItem: matsItem,
        metaMatsCount: matsCount,
        metaCardsItem: cardsItem,
        metaCardsCount: cardsCount,
      });
    }
  }

  function selectNode(id) {
    if (selectedId) {
      if (nodeElById.get(selectedId)) nodeElById.get(selectedId).root.classList.remove("is-selected");
      if (groupFrameById.get(selectedId)) groupFrameById.get(selectedId).rect.classList.remove("is-selected");
    }
    selectedId = id || null;
    if (selectedId) {
      if (nodeElById.get(selectedId)) nodeElById.get(selectedId).root.classList.add("is-selected");
      if (groupFrameById.get(selectedId)) groupFrameById.get(selectedId).rect.classList.add("is-selected");
    }

    // Edges: highlight what is related to the selection to aid "advance organizer" scanning.
    const related = new Set();
    if (selectedId) {
      const selectedNode = nodeById.get(String(selectedId)) || null;
      const isGroup = selectedNode && String(selectedNode.type || "") === "choice_group";
      if (isGroup && !renderChoiceNodes) {
        const choice = selectedNode.choice || {};
        const memberIds = Array.isArray(choice.memberIds) ? choice.memberIds.map(String) : [];
        const memberSet = new Set(memberIds);
        for (const e of edgeEls) {
          if (memberSet.has(e.from) || memberSet.has(e.to)) related.add(e);
        }
      } else {
        for (const e of edgeEls) {
          if (e.from === selectedId || e.to === selectedId) related.add(e);
        }
      }
    }

    for (const e of edgeEls) {
      const isRel = related.has(e);
      const fromDone = lastRuntime?.completedById?.[String(e.from)] === true;
      const toUnlocked = lastRuntime?.unlockedById?.[String(e.to)] === true;
      const gateReady = Boolean(fromDone && toUnlocked);
      e.el.classList.toggle("is-related", isRel);
      e.el.classList.toggle("is-dim", selectedId ? !isRel : false);
      e.el.classList.toggle("is-in", selectedId ? e.to === selectedId && gateReady : false);
      e.el.classList.toggle("is-out", selectedId ? e.from === selectedId && gateReady : false);
      e.el.classList.toggle("is-in-pending", selectedId ? e.to === selectedId && !fromDone : false);
      e.el.classList.toggle("is-out-pending", selectedId ? e.from === selectedId && !fromDone : false);
    }

    // Intentionally do not dim nodes: only edges communicate focus/relations.
  }

  function setGraph(nextGraph) {
    graph = nextGraph;
    nodeById = new Map((graph.nodes || []).map((n) => [String(n.id), n]));
    cachedWorldBounds = null;
    renderBands();
    renderFrames();
    renderEdges();
    renderNodes();
    refreshWorldBounds();

    if (!autoFitOnSetGraph) return;

    // Ensure the whole graph is visible initially (important for an "advance organizer" overview).
    // Some pages resize the graph after CSS/layout settles; retry a few frames so we don't
    // "fit" against the default SVG size (which can make everything look empty/tiny).
    let tries = 0;
    let lastW = 0;
    let lastH = 0;
    const MAX_TRIES = 12;
    const MIN_STABLE_H = 220;

    function attemptFit() {
      tries += 1;
      const rect = svg.getBoundingClientRect();
      const vw = rect.width;
      const vh = rect.height;
      const sizeChanged = Math.abs(vw - lastW) > 1 || Math.abs(vh - lastH) > 1;
      lastW = vw;
      lastH = vh;

      resetView();

      if (tries < MAX_TRIES && (vh < MIN_STABLE_H || sizeChanged)) {
        requestAnimationFrame(attemptFit);
      }
    }

    requestAnimationFrame(attemptFit);
  }

  function update(runtime) {
    if (!graph) return;
    lastRuntime = runtime || null;

    // Update group frames (works even when group nodes are hidden).
    for (const n of graph.nodes || []) {
      if (String(n.type) !== "choice_group") continue;
      const gid = String(n.id);
      const fr = groupFrameById.get(gid);
      if (!fr) continue;
      const st = (runtime.statusById || {})[gid] || {};
      const status = String(st.status || "locked");
      fr.rect.classList.toggle("is-locked", status === "locked");
      fr.rect.classList.toggle("is-open", status === "open");
      fr.rect.classList.toggle("is-partial", status === "partial");
      fr.rect.classList.toggle("is-done", status === "done");

      fr.label.classList.toggle("is-open", status === "open");
      fr.label.classList.toggle("is-partial", status === "partial");
      fr.label.classList.toggle("is-done", status === "done");

      const choice = n.choice || {};
      const m = Array.isArray(choice.memberIds) ? choice.memberIds.length : 0;
      const nReq = Math.max(0, Number(choice.n || 0));
      const done = Number(st.doneMembers || 0);
      const required = Math.min(nReq, m);
      fr.label.textContent = required > 0 ? `Wahlpflicht: ${done}/${required} erledigt (aus ${m})` : `Wahlpflicht: optional (aus ${m})`;
    }

    for (const n of graph.nodes || []) {
      const id = String(n.id);
      const el = nodeElById.get(id);
      if (!el) continue;
      const st = (runtime.statusById || {})[id] || {};
      const status = String(st.status || "locked");
      const sl = statusLabel(status);
      const ep = (runtime.edgePrereqProgress || {})[id] || null;

      el.root.classList.toggle("is-locked", status === "locked");
      el.root.classList.toggle("is-open", status === "open");
      el.root.classList.toggle("is-partial", status === "partial");
      el.root.classList.toggle("is-done", status === "done");
      el.root.setAttribute("aria-disabled", status === "locked" ? "true" : "false");

      if (el.badge) {
        const showBadge = status === "locked" || status === "done";
        el.badge.setAttribute("display", showBadge ? "" : "none");
      }

      if (el.badgeLock) el.badgeLock.setAttribute("display", status === "locked" ? "" : "none");
      if (el.badgeDone) el.badgeDone.setAttribute("display", status === "done" ? "" : "none");

      if (el.badgeRing && el.badgeRingProgress) {
        const total = Number(ep?.total || 0);
        const required = Number(ep?.required || 0);
        const done = Number(ep?.done || 0);
        const showBadge = status === "locked" || status === "done";
        const showGate = status === "locked" && total > 1 && required > 1;

        el.badgeRing.setAttribute("display", showBadge ? "" : "none");
        el.badgeRingProgress.setAttribute("display", showGate ? "" : "none");

        const pct = showGate && required > 0 ? clamp(done / required, 0, 1) : 0;
        el.badgeRingProgress.setAttribute("stroke-dashoffset", String(NODE_BADGE_RING_CIRC * (1 - pct)));
      }

      // Subline: keep it short and ASCII-only.
      const type = String(n.type || "");
      if (type === "choice_group") {
        if (el.meta) el.meta.setAttribute("display", "none");
        el.sub.setAttribute("display", "");
        const choice = n.choice || {};
        const m = Array.isArray(choice.memberIds) ? choice.memberIds.length : 0;
        const nReq = Math.max(0, Number(choice.n || 0));
        const done = Number(st.doneMembers || 0);
        const required = Math.min(nReq, m);
        el.sub.textContent = m > 0 ? (required > 0 ? `${done}/${required} erledigt (aus ${m})` : `optional (aus ${m})`) : "Gruppe";

        if (el.tooltip) {
          el.tooltip.textContent = `${String(n.title || id)} (${sl})`;
        }
      } else if (type === "flashcards") {
        if (el.meta) el.meta.setAttribute("display", "none");
        el.sub.setAttribute("display", "");
        const pct = Math.round(Number(st.strength || 0) * 100);
        el.sub.textContent = `Sicherheit: ${pct}%`;

        if (el.tooltip) {
          el.tooltip.textContent = `${String(n.title || id)} (${sl}) — Sicherheit: ${pct}%`;
        }
      } else {
        const done = Number(st.doneTasks || 0);
        const total = Number(st.totalTasks || 0);
        const mats = Array.isArray(n.materials) ? n.materials.length : 0;
        const cards = Array.isArray(n.cards) ? n.cards.length : 0;

        // Use pictograms + counts instead of dense text ("advance organizer" readability).
        if (el.meta) {
          el.meta.setAttribute("display", "");
          el.sub.setAttribute("display", "none");

          const showTasks = total > 0;
          const showMats = mats > 0;
          const showCards = cards > 0;

          if (el.metaTasksItem) el.metaTasksItem.style.display = showTasks ? "" : "none";
          if (el.metaMatsItem) el.metaMatsItem.style.display = showMats ? "" : "none";
          if (el.metaCardsItem) el.metaCardsItem.style.display = showCards ? "" : "none";

          if (el.metaTasksCount) el.metaTasksCount.textContent = showTasks ? `${done}/${total}` : "";
          if (el.metaMatsCount) el.metaMatsCount.textContent = showMats ? String(mats) : "";
          if (el.metaCardsCount) el.metaCardsCount.textContent = showCards ? String(cards) : "";

          const any = showTasks || showMats || showCards;
          el.meta.style.opacity = any ? "1" : "0";
        } else {
          // Fallback for older renderers.
          const parts = [];
          if (total > 0) parts.push(`${done}/${total}`);
          if (mats > 0) parts.push(`${mats} Mat.`);
          if (cards > 0) parts.push(`${cards} Karten`);
          el.sub.textContent = parts.join(" | ");
        }

        if (el.tooltip) {
          const parts = [];
          const totalPrereq = Number(ep?.total || 0);
          const requiredPrereq = Number(ep?.required || 0);
          const donePrereq = Number(ep?.done || 0);
          if (status === "locked" && totalPrereq > 1 && requiredPrereq > 1) {
            parts.push(`Voraussetzungen: ${Math.min(donePrereq, requiredPrereq)}/${Math.min(requiredPrereq, totalPrereq)}`);
          }
          if (total > 0) parts.push(`Aufgaben: ${Math.min(done, total)}/${total}`);
          if (mats > 0) parts.push(`Materialien: ${mats}`);
          if (cards > 0) parts.push(`Karteikarten: ${cards}`);
          const suffix = parts.length ? ` — ${parts.join(", ")}` : "";
          el.tooltip.textContent = `${String(n.title || id)} (${sl})${suffix}`;
        }
      }
    }

    // Re-apply selection highlighting so edges reflect updated completion/unlock state.
    if (selectedId) selectNode(selectedId);
  }

  // ---------------------------------------------------------------------------
  // Pan/zoom + (optional) node drag for authoring.
  // ---------------------------------------------------------------------------

  let pointer = null;
  let dragLayoutRaf = null;
  let lastDragId = null;
  const MOVE_THRESHOLD_PX = 4;
  let suppressClickUntil = 0;
  let pinch = null;
  const touchPoints = new Map(); // pointerId -> { x, y }

  function pointerDown(evt) {
    // Ignore right clicks
    if (evt.button !== 0) return;

    const rect = svg.getBoundingClientRect();

    if (evt.pointerType === "touch") {
      touchPoints.set(evt.pointerId, { x: evt.clientX, y: evt.clientY });
      if (touchPoints.size === 2) {
        const [id1, id2] = Array.from(touchPoints.keys());
        const p1 = touchPoints.get(id1);
        const p2 = touchPoints.get(id2);
        if (p1 && p2) {
          const center = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
          const startWorld = {
            x: (center.x - rect.left - tx) / k,
            y: (center.y - rect.top - ty) / k,
          };
          pinch = {
            ids: [id1, id2],
            startDist: Math.max(1, Math.hypot(p2.x - p1.x, p2.y - p1.y)),
            startK: k,
            startWorld,
          };
          pointer = null;
          startInteracting();
          svg.setPointerCapture(id1);
          svg.setPointerCapture(id2);
          evt.preventDefault();
          return;
        }
      }
    }

    const targetNode = evt.target && evt.target.closest ? evt.target.closest("[data-node-id]") : null;
    const startNodeId = targetNode ? String(targetNode.getAttribute("data-node-id") || "") : null;
    const allowDrag = typeof onNodePositionChange === "function";

    if (allowDrag && targetNode) {
      const id = String(targetNode.getAttribute("data-node-id") || "");
      pointer = {
        mode: "drag",
        id,
        startClient: { x: evt.clientX, y: evt.clientY },
        startWorld: clientToWorld({ x: evt.clientX, y: evt.clientY }, rect),
        startNode: { x: Number(nodeById.get(id)?.x || 0), y: Number(nodeById.get(id)?.y || 0) },
        moved: false,
        startNodeId,
        pointerId: evt.pointerId,
      };
      svg.setPointerCapture(evt.pointerId);
      evt.preventDefault();
      return;
    }

    pointer = {
      mode: "pan",
      startClient: { x: evt.clientX, y: evt.clientY },
      startTx: tx,
      startTy: ty,
      moved: false,
      startNodeId,
      pointerId: evt.pointerId,
    };
    svg.setPointerCapture(evt.pointerId);
    evt.preventDefault();
  }

  function pointerMove(evt) {
    if (pinch && evt.pointerType === "touch") {
      if (!touchPoints.has(evt.pointerId)) return;
      touchPoints.set(evt.pointerId, { x: evt.clientX, y: evt.clientY });
      const [id1, id2] = pinch.ids;
      const p1 = touchPoints.get(id1);
      const p2 = touchPoints.get(id2);
      if (!p1 || !p2) return;

      const dist = Math.max(1, Math.hypot(p2.x - p1.x, p2.y - p1.y));
      const rect = svg.getBoundingClientRect();
      const center = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      const nextK = clamp(pinch.startK * (dist / pinch.startDist), minZoom, MAX_ZOOM);
      if (nextK !== k) k = nextK;
      tx = center.x - rect.left - pinch.startWorld.x * k;
      ty = center.y - rect.top - pinch.startWorld.y * k;
      clampTransform(null, rect);
      scheduleTransform();
      return;
    }

    if (!pointer) return;
    if (pointer.pointerId !== evt.pointerId) return;

    const rect = svg.getBoundingClientRect();

    if (!pointer.moved) {
      const dx = evt.clientX - pointer.startClient.x;
      const dy = evt.clientY - pointer.startClient.y;
      if (Math.hypot(dx, dy) < MOVE_THRESHOLD_PX) return;
      pointer.moved = true;
      startInteracting();

      // Rebase so the content doesn't "jump" when the threshold is crossed.
      if (pointer.mode === "pan") {
        pointer.startClient = { x: evt.clientX, y: evt.clientY };
        pointer.startTx = tx;
        pointer.startTy = ty;
      } else if (pointer.mode === "drag") {
        pointer.startClient = { x: evt.clientX, y: evt.clientY };
        pointer.startWorld = clientToWorld({ x: evt.clientX, y: evt.clientY }, rect);
        const n = nodeById.get(pointer.id);
        if (n) pointer.startNode = { x: Number(n.x || 0), y: Number(n.y || 0) };
      }
    }

    if (pointer.mode === "pan") {
      const dx = evt.clientX - pointer.startClient.x;
      const dy = evt.clientY - pointer.startClient.y;
      const nextTx = pointer.startTx + dx;
      const nextTy = pointer.startTy + dy;
      clampTransform({ tx: nextTx, ty: nextTy }, rect);

      // Rebase so clamping doesn't create a "dead zone" near the edges.
      pointer.startClient = { x: evt.clientX, y: evt.clientY };
      pointer.startTx = tx;
      pointer.startTy = ty;
      scheduleTransform();
      return;
    }

    if (pointer.mode === "drag") {
      const world = clientToWorld({ x: evt.clientX, y: evt.clientY }, rect);
      const dx = world.x - pointer.startWorld.x;
      const dy = world.y - pointer.startWorld.y;
      const id = pointer.id;
      const n = nodeById.get(id);
      if (!n) return;
      n.x = pointer.startNode.x + dx;
      n.y = pointer.startNode.y + dy;

      // Update element positions and redraw edges/frames.
      const el = nodeElById.get(id);
      if (el) el.root.setAttribute("transform", `translate(${Number(n.x || 0)},${Number(n.y || 0)})`);
      lastDragId = id;
      if (!dragLayoutRaf) {
        dragLayoutRaf = requestAnimationFrame(() => {
          dragLayoutRaf = null;
          renderBands();
          renderFrames();
          renderEdges();
          refreshWorldBounds();
          if (typeof onNodePositionChange === "function" && lastDragId) {
            const nn = nodeById.get(String(lastDragId));
            if (nn) onNodePositionChange(String(lastDragId), { x: nn.x, y: nn.y });
          }
        });
      }
    }
  }

  function pointerUp(evt) {
    if (evt.pointerType === "touch") {
      touchPoints.delete(evt.pointerId);
      if (pinch && pinch.ids.includes(evt.pointerId)) {
        pinch = null;
        pointer = null;
        stopInteracting();
        return;
      }
    }
    if (!pointer) return;
    if (pointer.pointerId !== evt.pointerId) return;

    // Robust node "tap/click": pointer capture can prevent the normal click event
    // from reaching the node, so we treat a non-moved pointer-up on a node as a click.
    if (!pointer.moved && pointer.mode === "pan" && pointer.startNodeId) {
      suppressClickUntil = performance.now() + 120;
      selectNode(pointer.startNodeId);
      onNodeClick(pointer.startNodeId, evt);
    }

    pointer = null;
    stopInteracting();
  }

  function normalizeWheelDelta(evt) {
    // Convert wheel delta to pixels (best effort).
    // 0 = pixel, 1 = line, 2 = page
    if (evt.deltaMode === 1) return 16;
    if (evt.deltaMode === 2) return Math.max(240, svg.getBoundingClientRect().height);
    return 1;
  }

  function wheelPan(evt) {
    evt.preventDefault();
    startInteracting(140);
    const rect = svg.getBoundingClientRect();
    const m = normalizeWheelDelta(evt);
    let dx = evt.deltaX * m;
    let dy = evt.deltaY * m;
    // Some devices emulate horizontal scrolling via Shift+wheel.
    if (!dx && evt.shiftKey) {
      dx = dy;
      dy = 0;
    }
    tx -= dx;
    ty -= dy;
    clampTransform(null, rect);
    scheduleTransform();
  }

  function wheelZoom(evt) {
    evt.preventDefault();
    startInteracting(140);
    const rect = svg.getBoundingClientRect();
    const m = normalizeWheelDelta(evt);
    let delta = evt.deltaY * m;

    // Trackpads/pinch gestures emit very small deltas; boost them so zoom feels responsive.
    // Mouse wheels usually emit larger steps and don't need boosting.
    if (evt.deltaMode === 0) {
      const abs = Math.abs(delta);
      if (abs > 0 && abs < 2) delta *= 14;
      else if (abs < 8) delta *= 6;
      else if (abs < 24) delta *= 3;
    }

    // Guard against pathological spikes (e.g. some devices/browsers in "page" mode).
    delta = clamp(delta, -800, 800);

    // Smooth exponential zoom (similar feel to vis/d3): larger deltas zoom faster.
    const zoomFactor = Math.pow(2, -delta * 0.0025);
    const nextK = clamp(k * zoomFactor, minZoom, MAX_ZOOM);
    if (nextK === k) return;

    const p = { x: evt.clientX, y: evt.clientY };
    const before = clientToWorld(p, rect);
    k = nextK;
    const after = clientToWorld(p, rect);
    // Keep cursor anchored: adjust translation by the world delta.
    tx += (after.x - before.x) * k;
    ty += (after.y - before.y) * k;
    clampTransform(null, rect);
    scheduleTransform();
  }

  function zoomTo(nextK, { clientX, clientY } = {}) {
    if (!graph) return;
    startInteracting(180);
    const rect = svg.getBoundingClientRect();
    if (!(rect.width > 0) || !(rect.height > 0)) return;
    const cx = Number.isFinite(Number(clientX)) ? Number(clientX) : rect.left + rect.width / 2;
    const cy = Number.isFinite(Number(clientY)) ? Number(clientY) : rect.top + rect.height / 2;

    const anchor = { x: cx, y: cy };
    const before = clientToWorld(anchor, rect);
    k = clamp(safeNum(nextK), minZoom, MAX_ZOOM);
    const after = clientToWorld(anchor, rect);
    tx += (after.x - before.x) * k;
    ty += (after.y - before.y) * k;
    clampTransform(null, rect);
    applyTransform();
  }

  function setTransform(next = {}, { clampToViewport = true } = {}) {
    if (!graph) return false;
    const rect = svg.getBoundingClientRect();
    if (!(rect.width > 0) || !(rect.height > 0)) return false;
    tx = safeNum(next.tx);
    ty = safeNum(next.ty);
    k = clamp(safeNum(next.k), minZoom, MAX_ZOOM);
    if (clampToViewport) clampTransform(null, rect);
    applyTransform();
    return true;
  }

  function wheel(evt) {
    if (!graph) return;

    // "Map" interaction (overview mode): wheel/trackpad pans the graph;
    // Ctrl/⌘ + wheel (and trackpad pinch, which typically sets ctrlKey) zooms.
    if (evt.ctrlKey || evt.metaKey) {
      wheelZoom(evt);
      return;
    }
    wheelPan(evt);
  }

  if (interaction === "map") {
    svg.addEventListener("pointerdown", pointerDown);
    svg.addEventListener("pointermove", pointerMove);
    svg.addEventListener("pointerup", pointerUp);
    svg.addEventListener("pointercancel", pointerUp);
    svg.addEventListener("wheel", wheel, { passive: false });
    svg.addEventListener("dblclick", () => resetView());
    svg.addEventListener("click", () => {
      if (performance.now() < suppressClickUntil) return;
      if (selectOnClick) selectNode(null);
    });
  } else {
    svg.addEventListener("click", () => {
      if (selectOnClick) selectNode(null);
    });
  }

  applyTransform();

  return {
    svg,
    setGraph,
    update,
    resetView,
    selectNode,
    zoomTo,
    setTransform,
    getTransform: () => ({ tx, ty, k }),
    getWorldBounds: () => getWorldBounds(),
    worldToClient,
    clientToWorld,
    fitToGraph,
    setShowPhaseBands: (on) => {
      showPhaseBands = on === true;
      renderBands();
    },
  };
}
