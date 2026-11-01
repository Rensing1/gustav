import type { ElkNode, ElkPort, ElkExtendedEdge } from "elkjs/lib/elk-api";
import { planPhaseRows, type ModuleEdge, type ModulePhase } from "./module-graph-rows";

export const MODULE_WIDTH = 248;
export const MODULE_HEIGHT = 104;
export type Point = { x: number; y: number };
export type ModuleGeometry = Point & { id: string; phaseId: string; rowIndex: number };
export type PhaseGeometry = Point & { id: string; width: number; height: number };
export type EdgeGeometry = { points: Point[]; category: "same-row" | "same-phase" | "cross-phase" };
export type ModularGeometry = {
  phases: PhaseGeometry[];
  modules: Map<string, ModuleGeometry>;
  edges: Map<string, EdgeGeometry>;
  railWidth: number;
};
export type ElkLayout = (graph: ElkNode) => Promise<ElkNode>;

const NODE_GAP = 60;
const LANE_GAP = 18;
const HEADER_HEIGHT = 90;
const HEADER_GAP = 42;
const ROW_GAP = 64;
const MIN_PHASE_WIDTH = 1180;
export const modularViewportVersion = "layout-2";
export const moduleEdgeKey = (edge: ModuleEdge) => `${edge.from}->${edge.to}`;

type Row = {
  phaseId: string;
  index: number;
  ids: string[];
  x: number;
  y: number;
  width: number;
  height: number;
  contentLeft: number;
  contentWidth: number;
  nodes: Map<string, Point>;
  internal: Map<string, Point[]>;
  incoming: Map<string, Point[]>;
  outgoing: Map<string, Point[]>;
};
type RowEdges = { internal: ModuleEdge[]; incoming: ModuleEdge[]; outgoing: ModuleEdge[] };

function translate(points: Point[], x: number, y: number): Point[] {
  return points.map((p) => ({ x: p.x + x, y: p.y + y }));
}

function edgePoints(edge: ElkExtendedEdge): Point[] {
  const section = edge.sections?.[0];
  if (!section) throw Error("ELK returned an incomplete edge");
  return [section.startPoint, ...(section.bendPoints ?? []), section.endPoint];
}

/** Fixed center ports match the existing card handles in both role renderers. */
function card(id: string): ElkNode {
  return {
    id, width: MODULE_WIDTH, height: MODULE_HEIGHT,
    layoutOptions: { "elk.portConstraints": "FIXED_POS" },
    ports: [
      { id: `${id}:in`, x: 0, y: MODULE_HEIGHT / 2, width: 0, height: 0, layoutOptions: { "elk.port.side": "WEST" } },
      { id: `${id}:out`, x: MODULE_WIDTH, y: MODULE_HEIGHT / 2, width: 0, height: 0, layoutOptions: { "elk.port.side": "EAST" } }
    ]
  };
}

function terminal(id: string, edges: ModuleEdge[], incoming: boolean): ElkNode {
  const ports: ElkPort[] = edges.map((edge, i) => ({
    id: `${id}:${moduleEdgeKey(edge)}`, x: incoming ? 1 : 0, y: (i + 1) * LANE_GAP,
    width: 0, height: 0, layoutOptions: { "elk.port.side": incoming ? "EAST" : "WEST" }
  }));
  return {
    id, width: 1, height: (edges.length + 1) * LANE_GAP, ports,
    layoutOptions: { "elk.portConstraints": "FIXED_POS", "elk.layered.layering.layerConstraint": incoming ? "FIRST" : "LAST" }
  };
}

/** Let ELK route all attachments inside a row; only empty gutters connect rows. */
async function layoutRow(row: Row, { internal, incoming, outgoing }: RowEdges, layout: ElkLayout) {
  const entry = `entry:${row.phaseId}:${row.index}`;
  const exit = `exit:${row.phaseId}:${row.index}`;
  const children = row.ids.map(card);
  if (incoming.length) children.unshift(terminal(entry, incoming, true));
  if (outgoing.length) children.push(terminal(exit, outgoing, false));
  const elkEdges: ElkExtendedEdge[] = internal.map((edge) => ({
    id: moduleEdgeKey(edge), sources: [`${edge.from}:out`], targets: [`${edge.to}:in`]
  }));
  // Invisible ordering edges keep an independent grid row horizontal. They
  // exist only in the layout input and never become prerequisites or UI edges.
  if (internal.length === 0) {
    row.ids.slice(1).forEach((id, i) => elkEdges.push({
      id: `grid:${i}`, sources: [`${row.ids[i]}:out`], targets: [`${id}:in`]
    }));
  }
  incoming.forEach((edge) => elkEdges.push({
    id: `in:${moduleEdgeKey(edge)}`, sources: [`${entry}:${moduleEdgeKey(edge)}`], targets: [`${edge.to}:in`]
  }));
  outgoing.forEach((edge) => elkEdges.push({
    id: `out:${moduleEdgeKey(edge)}`, sources: [`${edge.from}:out`], targets: [`${exit}:${moduleEdgeKey(edge)}`]
  }));
  const result = await layout({
    id: `row:${row.phaseId}:${row.index}`, children, edges: elkEdges,
    layoutOptions: {
      "elk.algorithm": "layered", "elk.direction": "RIGHT", "elk.edgeRouting": "ORTHOGONAL",
      "elk.randomSeed": "1", "elk.spacing.nodeNode": String(NODE_GAP),
      "elk.layered.spacing.nodeNodeBetweenLayers": String(NODE_GAP),
      "elk.layered.crossingMinimization.forceNodeModelOrder": "true",
      "elk.padding": "[top=12,left=12,bottom=12,right=12]"
    }
  });
  if (!Number.isFinite(result.width) || !Number.isFinite(result.height)) throw Error("ELK returned incomplete row bounds");
  row.width = result.width!;
  row.height = result.height!;
  for (const node of result.children ?? []) {
    if (row.ids.includes(node.id)) {
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) throw Error("ELK returned incomplete module coordinates");
      row.nodes.set(node.id, { x: node.x!, y: node.y! });
    }
  }
  if (row.nodes.size !== row.ids.length) throw Error("ELK omitted a module");
  row.contentLeft = Math.min(...[...row.nodes.values()].map((point) => point.x));
  row.contentWidth = Math.max(...[...row.nodes.values()].map((point) => point.x + MODULE_WIDTH)) - row.contentLeft;
  for (const edge of result.edges ?? []) {
    if (edge.id.startsWith("in:")) row.incoming.set(edge.id.slice(3), edgePoints(edge));
    else if (edge.id.startsWith("out:")) row.outgoing.set(edge.id.slice(4), edgePoints(edge));
    else if (!edge.id.startsWith("grid:")) row.internal.set(edge.id, edgePoints(edge));
  }
}

/**
 * Compute one role-independent map from authorized modular graph data.
 * Coordinates include routing space, so overview/focus fits the actual paths.
 * ELK handles row interiors; explicit empty rails make returns predictable and
 * avoid maintaining a second general-purpose obstacle-routing algorithm.
 */
export async function layoutModularGraph(phases: ModulePhase[], edges: ModuleEdge[], layout: ElkLayout): Promise<ModularGeometry> {
  const ordered = [...phases].sort((a, b) => a.position - b.position || a.id.localeCompare(b.id));
  const sortedEdges = [...edges].sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to));
  const rowsByPhase = new Map<string, Row[]>();
  const rowByModule = new Map<string, Row>();
  for (const phase of ordered) {
    const rows = planPhaseRows(phase.modules, sortedEdges).map((ids, index): Row => ({
      phaseId: phase.id, index, ids, x: 0, y: 0, width: 0, height: 0, contentLeft: 0, contentWidth: 0,
      nodes: new Map(), internal: new Map(), incoming: new Map(), outgoing: new Map()
    }));
    rowsByPhase.set(phase.id, rows);
    for (const row of rows) for (const id of row.ids) rowByModule.set(id, row);
  }
  for (const edge of sortedEdges) {
    if (!rowByModule.has(edge.from) || !rowByModule.has(edge.to)) throw Error("Module edge has a missing endpoint");
  }
  const rows = [...rowsByPhase.values()].flat();
  const rowEdges = new Map(rows.map((row) => [row, { internal: [], incoming: [], outgoing: [] } as RowEdges]));
  const external: ModuleEdge[] = [];
  for (const edge of sortedEdges) {
    const from = rowByModule.get(edge.from)!, to = rowByModule.get(edge.to)!;
    if (from === to) rowEdges.get(from)!.internal.push(edge);
    else {
      rowEdges.get(from)!.outgoing.push(edge);
      rowEdges.get(to)!.incoming.push(edge);
      external.push(edge);
    }
  }
  // The worker already serializes calculations; keeping row requests sequential
  // also limits peak memory for large units.
  for (const row of rows) await layoutRow(row, rowEdges.get(row)!, layout);
  const crossPhase = external.filter((e) => rowByModule.get(e.from)!.phaseId !== rowByModule.get(e.to)!.phaseId);
  const crossPhaseLane = new Map(crossPhase.map((edge, i) => [moduleEdgeKey(edge), i + 1]));
  const railWidth = Math.max(72, (crossPhase.length + 2) * LANE_GAP);
  const phaseGap = Math.max(40, (crossPhase.length + 2) * LANE_GAP);
  // Center visible cards, not asymmetric invisible entry/exit terminals.
  // Reserve the larger terminal margin on both sides so every path still fits.
  const contentWidth = Math.max(MODULE_WIDTH, ...rows.map((row) => row.contentWidth
    + 2 * Math.max(row.contentLeft, row.width - row.contentLeft - row.contentWidth)));
  const width = Math.max(MIN_PHASE_WIDTH, contentWidth + railWidth * 2 + 120);
  const result: ModularGeometry = { phases: [], modules: new Map(), edges: new Map(), railWidth };
  let phaseY = 24;
  for (const phase of ordered) {
    let rowY = HEADER_HEIGHT + HEADER_GAP;
    const phaseRows = rowsByPhase.get(phase.id)!;
    const phaseContentWidth = Math.max(MODULE_WIDTH, ...phaseRows.map((row) => row.contentWidth));
    for (const row of phaseRows) {
      // Center the phase's content as one block; short continuation rows still
      // begin at its left edge instead of drifting back towards the middle.
      row.x = (width - phaseContentWidth) / 2 - row.contentLeft;
      row.y = rowY;
      for (const [id, point] of row.nodes) result.modules.set(id, {
        id, phaseId: phase.id, rowIndex: row.index, x: row.x + point.x, y: row.y + point.y
      });
      rowY += row.height + ROW_GAP;
    }
    const height = Math.max(HEADER_HEIGHT + HEADER_GAP + MODULE_HEIGHT + 24, rowY - (phaseRows.length ? ROW_GAP : 0) + 24);
    result.phases.push({ id: phase.id, x: 20, y: phaseY, width, height });
    phaseY += height + phaseGap;
  }
  const phaseById = new Map(result.phases.map((p) => [p.id, p]));
  for (const edge of sortedEdges) {
    const key = moduleEdgeKey(edge);
    const source = rowByModule.get(edge.from)!, target = rowByModule.get(edge.to)!;
    const sourcePhase = phaseById.get(source.phaseId)!, targetPhase = phaseById.get(target.phaseId)!;
    if (source === target) {
      result.edges.set(key, { category: "same-row", points: translate(source.internal.get(key)!, sourcePhase.x + source.x, sourcePhase.y + source.y) });
      continue;
    }
    const from = translate(source.outgoing.get(key)!, sourcePhase.x + source.x, sourcePhase.y + source.y);
    const to = translate(target.incoming.get(key)!, targetPhase.x + target.x, targetPhase.y + target.y);
    const first = from.at(-1)!, last = to[0];
    const cross = source.phaseId !== target.phaseId;
    const lane = cross ? crossPhaseLane.get(key)! : 1;
    const right = sourcePhase.x + width - lane * LANE_GAP;
    const left = targetPhase.x + lane * LANE_GAP;
    const middleY = cross
      ? sourcePhase.y + sourcePhase.height + lane * LANE_GAP
      : sourcePhase.y + source.y + source.height + ROW_GAP / 2;
    result.edges.set(key, {
      category: cross ? "cross-phase" : "same-phase",
      points: [...from, { x: right, y: first.y }, { x: right, y: middleY },
        { x: left, y: middleY }, { x: left, y: last.y }, ...to]
    });
  }
  return result;
}
