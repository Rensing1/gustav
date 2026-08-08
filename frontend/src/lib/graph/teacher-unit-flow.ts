import { MarkerType, Position, type Edge, type Node } from "@xyflow/svelte";
import type { SubmitFunction } from "@sveltejs/kit";

import type {
  TeacherUnitWorkspaceEdge,
  TeacherUnitWorkspaceGraphPhase,
  TeacherUnitWorkspaceModuleItem,
  TeacherUnitWorkspaceSectionItem,
  TeacherUnitWorkspaceSelection,
  TeacherUnitWorkspaceView
} from "$lib/types/home";

export const FLOW_NODE_WIDTH = 248;
export const FLOW_NODE_HEIGHT = 104;
const LINEAR_STAGE_PADDING_X = 88;
const LINEAR_STAGE_PADDING_Y = 56;
const MODULAR_STAGE_PADDING_X = 20;
const MODULAR_STAGE_PADDING_Y = 24;
const PHASE_HEADER_WIDTH_MIN = 1180;
const PHASE_HEADER_HEIGHT = 90;
const PHASE_HEADER_TO_MODULES_GAP_Y = 18;
const PHASE_GAP_Y = 40;
const PHASE_SIDE_GUTTER = 72;
const MODULAR_NODE_GAP_X = 60;
const MODULAR_NODE_LEVEL_GAP_Y = 140;
const MODULAR_EDGE_LANE_OFFSET = 18;
const PHASE_RAIL_GUTTER = 24;
const PHASE_MAX_COLUMNS_PER_ROW = 3;

type ElkLike = {
  layout: (graph: unknown) => Promise<unknown>;
};

let elkPromise: Promise<ElkLike> | undefined;

async function getElk(): Promise<ElkLike> {
  if (!elkPromise) {
    elkPromise = Promise.all([
      import("elkjs/lib/elk-api.js"),
      import("elkjs/lib/elk-worker.min.js?url")
    ])
      .then(([module, worker]) => new module.default({ workerUrl: worker.default }) as unknown as ElkLike)
      .catch((error: unknown) => {
        // A failed lazy load must remain retryable after a transient network error.
        elkPromise = undefined;
        throw error;
      });
  }
  return elkPromise;
}

export type TeacherFlowNodeData = {
  kind: "section" | "module" | "phase";
  title: string;
  kicker: string;
  meta: string;
  selectHref?: string | null;
  editorHref?: string | null;
  quickHref?: string | null;
  createHref?: string | null;
  createLabel?: string | null;
  phaseId?: string | null;
  bandHeight?: number | null;
  position?: number | null;
  connectable?: boolean;
  compact?: boolean;
};

export type TeacherFlowNode = Node<TeacherFlowNodeData, "unitNode" | "phaseBand">;
export type TeacherFlowEdgeData = {
  from: string;
  to: string;
  enhanceGraphForm?: SubmitFunction;
};
export type SmoothStepPathOptionsLike = {
  offset?: number;
  borderRadius?: number;
  centerX?: number;
};

export type TeacherFlowEdge = Edge<TeacherFlowEdgeData> & {
  pathOptions?: SmoothStepPathOptionsLike;
};

export function formatGraphCount(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function formatGraphCounts(materialsCount: number, tasksCount: number): string {
  return `${formatGraphCount(materialsCount, "Material", "Materialien")} · ${formatGraphCount(tasksCount, "Aufgabe", "Aufgaben")}`;
}

type ElkNode = { id: string; x?: number; y?: number; width?: number; height?: number };
type ModulePosition = {
  x: number;
  y: number;
  phaseId: string;
  rowIndex: number;
};

type PhaseLayout = {
  width: number;
  height: number;
  positions: Map<string, ModulePosition>;
};

type PhaseGraphIndexes = {
  outgoingBySource: Map<string, string[]>;
  indegree: Map<string, number>;
  outdegree: Map<string, number>;
};

function selectedSectionId(selection: TeacherUnitWorkspaceSelection): string | null {
  return selection.kind === "section" ? selection.section.id : null;
}

function selectedPhaseId(selection: TeacherUnitWorkspaceSelection): string | null {
  return selection.kind === "phase" ? selection.phase.id : null;
}

function selectedModuleId(selection: TeacherUnitWorkspaceSelection): string | null {
  return selection.kind === "module" ? selection.module.id : null;
}

function selectedEdge(selection: TeacherUnitWorkspaceSelection): TeacherUnitWorkspaceEdge | null {
  return selection.kind === "edge"
    ? { from: selection.edge.from_id, to: selection.edge.to_id }
    : null;
}

function equalsEdge(a: TeacherUnitWorkspaceEdge | null, b: TeacherUnitWorkspaceEdge): boolean {
  return Boolean(a && a.from === b.from && a.to === b.to);
}

function buildEdgeIndexes(edges: TeacherUnitWorkspaceEdge[]) {
  const outgoing = new Map<string, Set<string>>();
  const incoming = new Map<string, Set<string>>();

  for (const edge of edges) {
    outgoing.set(edge.from, new Set([...(outgoing.get(edge.from) ?? new Set<string>()), edge.to]));
    incoming.set(edge.to, new Set([...(incoming.get(edge.to) ?? new Set<string>()), edge.from]));
  }

  return { outgoing, incoming };
}

function moduleFocusState(
  moduleId: string,
  selection: TeacherUnitWorkspaceSelection,
  edgeIndexes: ReturnType<typeof buildEdgeIndexes>,
  phaseId: string
): "active" | "context" | "muted" | "default" {
  if (selection.kind === "none") {
    return "default";
  }

  if (selection.kind === "module") {
    if (selection.module.id === moduleId) {
      return "active";
    }

    const related = edgeIndexes.outgoing.get(selection.module.id)?.has(moduleId)
      || edgeIndexes.incoming.get(selection.module.id)?.has(moduleId);
    return related ? "context" : "muted";
  }

  if (selection.kind === "edge") {
    if (selection.edge.from_id === moduleId || selection.edge.to_id === moduleId) {
      return "active";
    }

    const touchesSelectedEndpoints =
      edgeIndexes.outgoing.get(selection.edge.from_id)?.has(moduleId)
      || edgeIndexes.incoming.get(selection.edge.from_id)?.has(moduleId)
      || edgeIndexes.outgoing.get(selection.edge.to_id)?.has(moduleId)
      || edgeIndexes.incoming.get(selection.edge.to_id)?.has(moduleId);

    return touchesSelectedEndpoints ? "context" : "muted";
  }

  if (selection.kind === "phase") {
    return selection.phase.id === phaseId ? "context" : "muted";
  }

  return "default";
}

function phaseFocusState(phaseId: string, selection: TeacherUnitWorkspaceSelection): "active" | "context" | "muted" | "default" {
  if (selection.kind === "none") {
    return "default";
  }

  if (selection.kind === "phase") {
    return selection.phase.id === phaseId ? "active" : "muted";
  }

  if (selection.kind === "module") {
    return selection.module.phase_id === phaseId ? "context" : "muted";
  }

  return "default";
}

async function layoutLinearNodes(items: TeacherUnitWorkspaceSectionItem[]): Promise<Map<string, { x: number; y: number }>> {
  const elk = await getElk();
  const graph = {
    id: "linear",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.layered.spacing.nodeNodeBetweenLayers": "48",
      "elk.spacing.nodeNode": "44"
    },
    children: items.map((item) => ({
      id: item.id,
      width: FLOW_NODE_WIDTH,
      height: FLOW_NODE_HEIGHT
    })),
    edges: items.slice(1).map((item, index) => ({
      id: `linear-${items[index].id}-${item.id}`,
      sources: [items[index].id],
      targets: [item.id]
    }))
  };

  const layout = (await elk.layout(graph)) as { children?: ElkNode[] };
  return new Map((layout.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]));
}

function layoutPhaseModules(
  phase: TeacherUnitWorkspaceGraphPhase,
  allEdges: TeacherUnitWorkspaceEdge[]
): PhaseLayout {
  const phaseModuleIds = new Set(phase.modules.map((module) => module.id));
  const internalEdges = allEdges.filter((edge) => phaseModuleIds.has(edge.from) && phaseModuleIds.has(edge.to));
  const modules = phase.modules.slice().sort((left, right) => left.position_in_phase - right.position_in_phase);
  const indexes = buildPhaseGraphIndexes(modules, internalEdges);
  const simpleChain =
    modules.length <= PHASE_MAX_COLUMNS_PER_ROW
    && isSimplePhaseChain(modules, internalEdges, indexes);

  return simpleChain
    ? layoutSimplePhaseRow(phase.id, modules)
    : layoutLayeredPhaseRows(phase.id, modules, indexes);
}

function buildPhaseGraphIndexes(
  modules: TeacherUnitWorkspaceModuleItem[],
  internalEdges: TeacherUnitWorkspaceEdge[]
): PhaseGraphIndexes {
  const outgoingBySource = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  const outdegree = new Map<string, number>();

  for (const module of modules) {
    outgoingBySource.set(module.id, []);
    indegree.set(module.id, 0);
    outdegree.set(module.id, 0);
  }

  for (const edge of internalEdges) {
    if (!outgoingBySource.has(edge.from) || !indegree.has(edge.to)) {
      continue;
    }

    outgoingBySource.set(edge.from, [...(outgoingBySource.get(edge.from) ?? []), edge.to]);
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
    outdegree.set(edge.from, (outdegree.get(edge.from) ?? 0) + 1);
  }

  return { outgoingBySource, indegree, outdegree };
}

function isSimplePhaseChain(
  modules: TeacherUnitWorkspaceModuleItem[],
  internalEdges: TeacherUnitWorkspaceEdge[],
  indexes: PhaseGraphIndexes
): boolean {
  if (modules.length <= 1) {
    return true;
  }

  if (internalEdges.length > Math.max(0, modules.length - 1)) {
    return false;
  }

  for (const module of modules) {
    if ((indexes.indegree.get(module.id) ?? 0) > 1 || (indexes.outdegree.get(module.id) ?? 0) > 1) {
      return false;
    }
  }

  return true;
}

function layoutSimplePhaseRow(
  phaseId: string,
  modules: TeacherUnitWorkspaceModuleItem[]
): PhaseLayout {
  const positions = new Map<string, ModulePosition>();

  modules.forEach((module, index) => {
    positions.set(module.id, {
      x: index * (FLOW_NODE_WIDTH + MODULAR_NODE_GAP_X),
      y: 0,
      phaseId,
      rowIndex: 0
    });
  });

  const contentWidth = Math.max(
    FLOW_NODE_WIDTH,
    modules.length === 0 ? FLOW_NODE_WIDTH : FLOW_NODE_WIDTH + Math.max(0, modules.length - 1) * (FLOW_NODE_WIDTH + MODULAR_NODE_GAP_X)
  );

  return {
    width: contentWidth + PHASE_SIDE_GUTTER * 2,
    height: FLOW_NODE_HEIGHT + PHASE_RAIL_GUTTER * 2,
    positions
  };
}

function layoutLayeredPhaseRows(
  phaseId: string,
  modules: TeacherUnitWorkspaceModuleItem[],
  indexes: PhaseGraphIndexes
): PhaseLayout {
  const indegree = new Map(indexes.indegree);
  const levelByModule = new Map<string, number>();
  const queue = modules
    .filter((module) => (indegree.get(module.id) ?? 0) === 0)
    .sort((left, right) => left.position_in_phase - right.position_in_phase)
    .map((module) => module.id);

  let head = 0;
  const seen = new Set<string>();
  while (head < queue.length) {
    const id = queue[head++];
    if (!id || seen.has(id)) {
      continue;
    }

    seen.add(id);
    const currentLevel = levelByModule.get(id) ?? 0;
    for (const successor of indexes.outgoingBySource.get(id) ?? []) {
      const nextLevel = currentLevel + 1;
      levelByModule.set(successor, Math.max(levelByModule.get(successor) ?? 0, nextLevel));
      const nextInDegree = Math.max(0, (indegree.get(successor) ?? 0) - 1);
      indegree.set(successor, nextInDegree);
      if (nextInDegree === 0 && !seen.has(successor)) {
        queue.push(successor);
      }
    }
  }

  for (const module of modules) {
    if (!levelByModule.has(module.id)) {
      levelByModule.set(module.id, 0);
    }
  }

  const modulesByLevel = new Map<number, TeacherUnitWorkspaceModuleItem[]>();
  for (const module of modules) {
    const level = levelByModule.get(module.id) ?? 0;
    const bucket = modulesByLevel.get(level) ?? [];
    bucket.push(module);
    modulesByLevel.set(level, bucket);
  }

  const positions = new Map<string, ModulePosition>();
  const levelWidths = new Map<number, number>();
  for (const [level, buckets] of modulesByLevel) {
    buckets.sort((left, right) => left.position_in_phase - right.position_in_phase);
    const rowWidth =
      buckets.length === 0 ? FLOW_NODE_WIDTH : (buckets.length - 1) * (FLOW_NODE_WIDTH + MODULAR_NODE_GAP_X) + FLOW_NODE_WIDTH;
    levelWidths.set(level, rowWidth);
  }

  const maxRowWidth = Math.max(FLOW_NODE_WIDTH, ...Array.from(levelWidths.values()));

  for (const [level, buckets] of modulesByLevel) {
    buckets.sort((left, right) => left.position_in_phase - right.position_in_phase);
    const rowWidth =
      buckets.length === 0 ? FLOW_NODE_WIDTH : (buckets.length - 1) * (FLOW_NODE_WIDTH + MODULAR_NODE_GAP_X) + FLOW_NODE_WIDTH;
    const rowOffset = Math.max(0, (maxRowWidth - rowWidth) / 2);

    buckets.forEach((module, index) => {
      positions.set(module.id, {
        x: rowOffset + index * (FLOW_NODE_WIDTH + MODULAR_NODE_GAP_X),
        y: level * MODULAR_NODE_LEVEL_GAP_Y,
        phaseId,
        rowIndex: level
      });
    });
  }

  const contentHeight = Math.max(
    FLOW_NODE_HEIGHT,
    ...Array.from(levelByModule.values(), (level) => level * MODULAR_NODE_LEVEL_GAP_Y + FLOW_NODE_HEIGHT)
  );

  return {
    width: maxRowWidth + PHASE_SIDE_GUTTER * 2,
    height: contentHeight + PHASE_RAIL_GUTTER * 2,
    positions
  };
}

function buildLinearEdges(items: TeacherUnitWorkspaceSectionItem[]): TeacherFlowEdge[] {
  return items.slice(1).map((item, index) => ({
    id: `linear:${items[index].id}->${item.id}`,
    source: items[index].id,
    target: item.id,
    type: "smoothstep",
    selectable: false,
    focusable: false,
    animated: false,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 16,
      height: 16
    },
    data: { from: items[index].id, to: item.id },
    class: "teacher-flow-edge teacher-flow-edge--linear"
  }));
}

function sectionNode(
  item: TeacherUnitWorkspaceSectionItem,
  x: number,
  y: number,
  selection: TeacherUnitWorkspaceSelection
): TeacherFlowNode {
  return {
    id: item.id,
    type: "unitNode",
    position: { x, y },
    width: FLOW_NODE_WIDTH,
    height: FLOW_NODE_HEIGHT,
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
    draggable: true,
    selectable: false,
    dragHandle: ".teacher-flow-unit-node__drag-handle",
    data: {
      kind: "section",
      title: item.title,
      kicker: `Abschnitt ${String(item.position).padStart(2, "0")}`,
      meta: formatGraphCounts(item.materials_count, item.tasks_count),
      selectHref: `?section=${encodeURIComponent(item.id)}`,
      editorHref: item.editor_href,
      position: item.position,
      connectable: false,
      compact: true
    },
    selected: selectedSectionId(selection) === item.id,
    class: "teacher-flow-node teacher-flow-node--section"
  };
}

function phaseNode(
  phase: TeacherUnitWorkspaceGraphPhase,
  width: number,
  height: number,
  y: number,
  selection: TeacherUnitWorkspaceSelection
): TeacherFlowNode {
  return {
    id: `phase:${phase.id}`,
    type: "phaseBand",
    position: { x: MODULAR_STAGE_PADDING_X, y },
    width,
    height,
    draggable: false,
    selectable: false,
    data: {
      kind: "phase",
      title: phase.title,
      kicker: `Phase ${phase.position}`,
      meta: `${phase.modules.length} Module`,
      selectHref: `?phase=${encodeURIComponent(phase.id)}`,
      createHref: `?phase=${encodeURIComponent(phase.id)}&create-module=1`,
      createLabel: "Modul hinzufügen",
      phaseId: phase.id,
      position: phase.position,
      bandHeight: height,
      compact: true
    },
    selected: selectedPhaseId(selection) === phase.id,
    class: `teacher-flow-phase teacher-flow-phase--${phaseFocusState(phase.id, selection)}`
  };
}

function moduleNode(
  module: TeacherUnitWorkspaceModuleItem,
  x: number,
  y: number,
  selection: TeacherUnitWorkspaceSelection,
  edgeIndexes: ReturnType<typeof buildEdgeIndexes>,
  phaseId: string
): TeacherFlowNode {
  const focusState = moduleFocusState(module.id, selection, edgeIndexes, phaseId);
  return {
    id: module.id,
    type: "unitNode",
    position: { x, y },
    width: FLOW_NODE_WIDTH,
    height: FLOW_NODE_HEIGHT,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    draggable: true,
    selectable: false,
    dragHandle: ".teacher-flow-unit-node__drag-handle",
    parentId: `phase:${phaseId}`,
    extent: "parent",
    data: {
      kind: "module",
      title: module.title,
      kicker: `Modul ${String(module.position_in_phase).padStart(2, "0")}`,
      meta: formatGraphCounts(module.materials_count, module.tasks_count),
      selectHref: `?module=${encodeURIComponent(module.id)}`,
      editorHref: module.editor_href,
      phaseId: module.phase_id,
      position: module.position_in_phase,
      connectable: true,
      compact: true
    },
    selected: selectedModuleId(selection) === module.id,
    class: `teacher-flow-node teacher-flow-node--module teacher-flow-node--${focusState}`,
    zIndex: 2
  };
}

function routeModularEdge(
  source: ModulePosition,
  target: ModulePosition
): {
  sourceHandle: string;
  targetHandle: string;
  bucket: string;
  category: "same-row" | "same-phase" | "cross-phase";
} {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const samePhase = source.phaseId === target.phaseId;
  const sameRow = samePhase && source.rowIndex === target.rowIndex;

  if (sameRow) {
    if (dx >= 0) {
      return {
        sourceHandle: "right-source",
        targetHandle: "left-target",
        bucket: `same-row:${source.phaseId}:${source.rowIndex}`,
        category: "same-row"
      };
    }
    return {
      sourceHandle: "left-source",
      targetHandle: "right-target",
      bucket: `same-row:${source.phaseId}:${source.rowIndex}`,
      category: "same-row"
    };
  }

  if (samePhase) {
    return {
      sourceHandle: dy >= 0 ? "bottom-source" : "top-source",
      targetHandle: dy >= 0 ? "top-target" : "bottom-target",
      bucket: `same-phase:${source.phaseId}:${Math.min(source.rowIndex, target.rowIndex)}:${Math.max(source.rowIndex, target.rowIndex)}`,
      category: "same-phase"
    };
  }

  return {
    sourceHandle: dy >= 0 ? "bottom-source" : "top-source",
    targetHandle: dy >= 0 ? "top-target" : "bottom-target",
    bucket: `cross-phase:${source.phaseId}:${target.phaseId}`,
    category: "cross-phase"
  };
}

function buildModularEdges(
  workspace: TeacherUnitWorkspaceView,
  modulePositions: Map<string, ModulePosition>,
  selection: TeacherUnitWorkspaceSelection
): TeacherFlowEdge[] {
  type RoutedModularEdge = { edge: TeacherFlowEdge; routeBucket: string; category: "same-row" | "same-phase" | "cross-phase" };
  const activeEdge = selectedEdge(selection);
  const activeModuleId = selectedModuleId(selection);
  const hasFocusedSelection =
    selection.kind === "module"
    || selection.kind === "edge"
    || selection.kind === "phase";
  const edgesWithBucket = (workspace.graph.edges ?? []).map((edge) => {
    const source = modulePositions.get(edge.from);
    const target = modulePositions.get(edge.to);
    const route = source && target ? routeModularEdge(source, target) : {
      sourceHandle: "right-source",
      targetHandle: "left-target",
      bucket: "default",
      category: "same-row"
    };
    const sourcePhaseId = source?.phaseId ?? null;
    const targetPhaseId = target?.phaseId ?? null;
    const isPhaseFocused =
      selection.kind === "phase" && sourcePhaseId === selection.phase.id && targetPhaseId === selection.phase.id;
    const isSelectedModuleRelated = activeModuleId && (edge.from === activeModuleId || edge.to === activeModuleId);
    const isSelectedEdgeRelated =
      selection.kind === "edge"
      && (
        edge.from === selection.edge.from_id
        || edge.to === selection.edge.to_id
        || edge.to === selection.edge.from_id
        || edge.from === selection.edge.to_id
      );
    const graphEdge: TeacherFlowEdge = {
      id: `edge:${edge.from}->${edge.to}`,
      source: edge.from,
      target: edge.to,
      sourceHandle: route.sourceHandle,
      targetHandle: route.targetHandle,
      type: "teacherEdge",
      selectable: false,
      focusable: true,
      animated: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 18,
        height: 18
      },
      data: {
        from: edge.from,
        to: edge.to
      },
      selected: equalsEdge(activeEdge, edge),
      pathOptions: {
        offset: 0
      },
      class: [
        "teacher-flow-edge",
        `teacher-flow-edge--${route.category}`,
        equalsEdge(activeEdge, edge)
          ? "teacher-flow-edge--selected"
          : selection.kind === "phase"
            ? isPhaseFocused
              ? "teacher-flow-edge--related"
              : "teacher-flow-edge--muted"
            : selection.kind === "edge"
              ? isSelectedEdgeRelated
                ? "teacher-flow-edge--related"
                : "teacher-flow-edge--muted"
            : activeModuleId && !isSelectedModuleRelated
            ? "teacher-flow-edge--muted"
            : hasFocusedSelection
              ? "teacher-flow-edge--related"
              : ""
      ]
        .filter(Boolean)
        .join(" ")
    };

    return {
      edge: graphEdge,
      routeBucket: route.bucket,
      category: route.category
    } as RoutedModularEdge;
  }) as RoutedModularEdge[];

  const edgeByBucket = new Map<TeacherFlowEdge, { bucket: string; category: "same-row" | "same-phase" | "cross-phase" }>();
  const edges = edgesWithBucket.map((item) => item.edge);
  const bucketed = new Map<string, TeacherFlowEdge[]>();
  for (const { edge, routeBucket, category } of edgesWithBucket) {
    edgeByBucket.set(edge, { bucket: routeBucket, category });
    const bucket = routeBucket ?? "default";
    const bucketEdges = bucketed.get(bucket) ?? [];
    bucketEdges.push(edge);
    bucketed.set(bucket, bucketEdges);
  }

  for (const bucketEdges of bucketed.values()) {
    bucketEdges.sort((left, right) => (left.source ?? "").localeCompare(right.source ?? ""));
    const total = bucketEdges.length;
    const center = (total - 1) / 2;
    bucketEdges.forEach((edge, index) => {
      const routeMeta = edgeByBucket.get(edge);
      const category = routeMeta?.category ?? "same-row";
      const offset = (index - center) * MODULAR_EDGE_LANE_OFFSET;
      edge.pathOptions =
        category === "same-row"
          ? { offset: offset * 0.45, borderRadius: 18 }
          : category === "same-phase"
            ? { offset, borderRadius: 18 }
            : { offset: offset * 1.35, borderRadius: 24 };
    });
  }

  return edges;
}


export async function buildTeacherUnitFlow(workspace: TeacherUnitWorkspaceView): Promise<{
  nodes: TeacherFlowNode[];
  edges: TeacherFlowEdge[];
}>;
export async function buildTeacherUnitFlow(
  workspace: TeacherUnitWorkspaceView,
  selection: TeacherUnitWorkspaceSelection
): Promise<{
  nodes: TeacherFlowNode[];
  edges: TeacherFlowEdge[];
}>;
export async function buildTeacherUnitFlow(
  workspace: TeacherUnitWorkspaceView,
  selection: TeacherUnitWorkspaceSelection = workspace.selection
): Promise<{
  nodes: TeacherFlowNode[];
  edges: TeacherFlowEdge[];
}> {
  if (workspace.graph.kind === "linear") {
    const sections = workspace.graph.nodes ?? [];
    const positions = await layoutLinearNodes(sections);
    const nodes = sections.map((section) => {
      const pos = positions.get(section.id) ?? { x: 0, y: 0 };
      return sectionNode(
        section,
        LINEAR_STAGE_PADDING_X + pos.x,
        LINEAR_STAGE_PADDING_Y + pos.y,
        selection
      );
    });
    return {
      nodes,
      edges: buildLinearEdges(sections)
    };
  }

  const phases = workspace.graph.phases ?? [];
  const graphEdges = workspace.graph.edges ?? [];
  const edgeIndexes = buildEdgeIndexes(graphEdges);
  const laneLayouts = phases.map((phase) => layoutPhaseModules(phase, graphEdges));
  const phaseHeaderWidth = Math.max(
    PHASE_HEADER_WIDTH_MIN,
    ...laneLayouts.map((lane) => lane.width + 120)
  );

  const nodes: TeacherFlowNode[] = [];
  const modulePositions = new Map<string, ModulePosition>();
  let currentY = MODULAR_STAGE_PADDING_Y;

  phases.forEach((phase, index) => {
    const lane = laneLayouts[index];
    const phaseHeight = PHASE_HEADER_HEIGHT + PHASE_HEADER_TO_MODULES_GAP_Y + Math.max(FLOW_NODE_HEIGHT, lane.height);
    nodes.push(phaseNode(phase, phaseHeaderWidth, phaseHeight, currentY, selection));

    phase.modules.forEach((module) => {
      const position = lane.positions.get(module.id) ?? {
        x: 0,
        y: 0,
        phaseId: phase.id,
        rowIndex: 0
      };
      const phaseInnerOffset = Math.max(0, (phaseHeaderWidth - lane.width) / 2);
      const relativeX = phaseInnerOffset + PHASE_SIDE_GUTTER + position.x;
      const relativeY = PHASE_HEADER_HEIGHT + PHASE_HEADER_TO_MODULES_GAP_Y + PHASE_RAIL_GUTTER + position.y;
      const absoluteX = MODULAR_STAGE_PADDING_X + relativeX;
      const absoluteY = currentY + relativeY;
      nodes.push(
        moduleNode(
          module,
          relativeX,
          relativeY,
          selection,
          edgeIndexes,
          phase.id
        )
      );
      modulePositions.set(module.id, { ...position, x: absoluteX, y: absoluteY });
    });

    currentY += phaseHeight + PHASE_GAP_Y;
  });

  return {
    nodes,
    edges: buildModularEdges(workspace, modulePositions, selection)
  };
}
