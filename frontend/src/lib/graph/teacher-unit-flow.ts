import { MarkerType, Position, type Edge, type Node } from "@xyflow/svelte";
import type { SubmitFunction } from "@sveltejs/kit";
import { getElk } from "./elk-layout";
import { layoutModularGraph, moduleEdgeKey, MODULE_WIDTH, MODULE_HEIGHT, type ModularGeometry, type Point } from "./module-graph-layout";
import type { ModularGeometryCache } from "./module-graph-cache";

import type {
  TeacherUnitWorkspaceEdge,
  TeacherUnitWorkspaceGraphPhase,
  TeacherUnitWorkspaceModuleItem,
  TeacherUnitWorkspaceSectionItem,
  TeacherUnitWorkspaceSelection,
  TeacherUnitWorkspaceView
} from "$lib/types/home";

export const FLOW_NODE_WIDTH = MODULE_WIDTH;
export const FLOW_NODE_HEIGHT = MODULE_HEIGHT;
const LINEAR_STAGE_PADDING_X = 88;
const LINEAR_STAGE_PADDING_Y = 56;

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
  headerInset?: number;
  phaseSelected?: boolean;
};

export type TeacherFlowNode = Node<TeacherFlowNodeData, "unitNode" | "phaseBand">;
export type TeacherFlowEdgeData = {
  from: string;
  to: string;
  enhanceGraphForm?: SubmitFunction;
  routePoints?: Point[];
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

function buildLinearEdges(items: TeacherUnitWorkspaceSectionItem[]): TeacherFlowEdge[] {
  return items.slice(1).map((item, index) => ({
    id: `linear:${items[index].id}->${item.id}`,
    source: items[index].id,
    target: item.id,
    ariaLabel: `Verbindung von ${items[index].title} nach ${item.title}`,
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
  selection: TeacherUnitWorkspaceSelection,
  headerInset: number
): TeacherFlowNode {
  return {
    id: `phase:${phase.id}`,
    type: "phaseBand",
    position: { x: 20, y },
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
      headerInset,
      phaseSelected: selectedPhaseId(selection) === phase.id,
      compact: true
    },
    // Selecting an XYFlow parent suppresses dragging its children. Phase
    // selection is a visual/editor state, never a group-drag selection.
    selected: false,
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

function buildModularEdges(
  workspace: TeacherUnitWorkspaceView,
  geometry: ModularGeometry,
  selection: TeacherUnitWorkspaceSelection
): TeacherFlowEdge[] {
  const moduleTitles = new Map((workspace.graph.phases ?? []).flatMap((phase) => phase.modules.map((module) => [module.id, module.title] as const)));
  const activeEdge = selectedEdge(selection);
  const activeModuleId = selectedModuleId(selection);
  const hasFocusedSelection =
    selection.kind === "module"
    || selection.kind === "edge"
    || selection.kind === "phase";
  return (workspace.graph.edges ?? []).map((edge) => {
    const route = geometry.edges.get(moduleEdgeKey(edge))!;
    const sourcePhaseId = geometry.modules.get(edge.from)?.phaseId ?? null;
    const targetPhaseId = geometry.modules.get(edge.to)?.phaseId ?? null;
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
      ariaLabel: `Verbindung von ${moduleTitles.get(edge.from) ?? "Modul"} nach ${moduleTitles.get(edge.to) ?? "Modul"}`,
      sourceHandle: "right-source",
      targetHandle: "left-target",
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
        to: edge.to,
        routePoints: route.points
      },
      selected: equalsEdge(activeEdge, edge),

      class: [
        "teacher-flow-edge",
        "teacher-flow-edge--routed",
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

    return graphEdge;
  });
}

export async function buildTeacherUnitFlow(
  workspace: TeacherUnitWorkspaceView,
  selection: TeacherUnitWorkspaceSelection = workspace.selection,
  getGeometry: ModularGeometryCache = layoutModularGraph
): Promise<{ nodes: TeacherFlowNode[]; edges: TeacherFlowEdge[] }> {
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

  const phases = [...(workspace.graph.phases ?? [])].sort((a, b) => a.position - b.position);
  const graphEdges = workspace.graph.edges ?? [];
  const edgeIndexes = buildEdgeIndexes(graphEdges);
  const elk = await getElk();
  const geometry = await getGeometry(phases, graphEdges, elk.layout.bind(elk));
  const nodes: TeacherFlowNode[] = [];
  for (const phase of phases) {
    const bounds = geometry.phases.find((item) => item.id === phase.id)!;
    nodes.push(phaseNode(phase, bounds.width, bounds.height, bounds.y, selection, geometry.railWidth));
    for (const module of phase.modules) {
      const position = geometry.modules.get(module.id)!;
      nodes.push(moduleNode(module, position.x, position.y, selection, edgeIndexes, phase.id));
    }
  }
  return { nodes, edges: buildModularEdges(workspace, geometry, selection) };
}
