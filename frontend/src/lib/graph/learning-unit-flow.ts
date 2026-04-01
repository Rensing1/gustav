import {
  buildTeacherUnitFlow,
  type TeacherFlowEdge,
  type TeacherFlowNode,
  type TeacherFlowNodeData
} from "$lib/graph/teacher-unit-flow";
import type { LearningUnitGraph, LearningUnitGraphModule } from "$lib/types/learning";
import type {
  TeacherUnitWorkspaceGraphPhase,
  TeacherUnitWorkspaceModuleItem,
  TeacherUnitWorkspaceSelection,
  TeacherUnitWorkspaceView
} from "$lib/types/home";
import type { SessionBootstrapUser } from "$lib/types/session-bootstrap";

export type LearningFlowNodeData = TeacherFlowNodeData & {
  status?: LearningUnitGraphModule["status"];
  progressLabel?: string;
  materialsLabel?: string;
  openable?: boolean;
  onSelect?: (() => void) | null;
};

export type LearningFlowNode = TeacherFlowNode & {
  data: LearningFlowNodeData;
};

function learnerSelection(graph: LearningUnitGraph, activeModuleId: string | null): TeacherUnitWorkspaceSelection {
  if (!activeModuleId) {
    return { kind: "none" };
  }

  const module = graph.modules.find((candidate) => candidate.id === activeModuleId);
  if (!module) {
    return { kind: "none" };
  }

  return {
    kind: "module",
    module: {
      id: module.id,
      title: module.title,
      phase_id: module.phase_id,
      position_in_phase: module.position_in_phase,
      required_prereq_count: module.required_prereq_count,
      materials_count: module.materials_count,
      tasks_count: module.tasks_total,
      editor_href: ""
    }
  };
}

function toTeacherPhases(graph: LearningUnitGraph): TeacherUnitWorkspaceGraphPhase[] {
  const modulesByPhaseId = new Map<string, TeacherUnitWorkspaceModuleItem[]>();

  for (const module of graph.modules) {
    const bucket = modulesByPhaseId.get(module.phase_id) ?? [];
    bucket.push({
      id: module.id,
      title: module.title,
      phase_id: module.phase_id,
      position_in_phase: module.position_in_phase,
      required_prereq_count: module.required_prereq_count,
      materials_count: module.materials_count,
      tasks_count: module.tasks_total,
      editor_href: ""
    });
    modulesByPhaseId.set(module.phase_id, bucket);
  }

  return graph.phases.map((phase) => ({
    id: phase.id,
    title: phase.title,
    position: phase.position,
    modules: (modulesByPhaseId.get(phase.id) ?? []).sort(
      (left, right) => left.position_in_phase - right.position_in_phase
    )
  }));
}

function toTeacherWorkspace(
  graph: LearningUnitGraph,
  user: SessionBootstrapUser,
  activeModuleId: string | null
): TeacherUnitWorkspaceView {
  return {
    user,
    unit: {
      id: graph.unit.id,
      title: graph.unit.title,
      unit_type: graph.unit.unit_type,
      edit_href: ""
    },
    counts: {
      sections_count: 0,
      phases_count: graph.phases.length,
      modules_count: graph.modules.length,
      courses_count: 0
    },
    graph: {
      kind: "modular",
      phases: toTeacherPhases(graph),
      edges: graph.edges.map((edge) => ({ from: edge.from, to: edge.to }))
    },
    selection: learnerSelection(graph, activeModuleId)
  };
}

export async function buildLearningUnitFlow(
  graph: LearningUnitGraph,
  user: SessionBootstrapUser,
  activeModuleId: string | null,
  onOpenModule: (moduleId: string) => void
): Promise<{ nodes: LearningFlowNode[]; edges: TeacherFlowEdge[] }> {
  const moduleById = new Map(graph.modules.map((module) => [module.id, module]));
  const teacherWorkspace = toTeacherWorkspace(graph, user, activeModuleId);
  const flow = await buildTeacherUnitFlow(teacherWorkspace);

  const nodes = flow.nodes.map((node) => {
    if (node.data.kind !== "module") {
      return {
        ...node,
        data: {
          ...node.data,
          selectHref: null,
          quickHref: null,
          editorHref: null,
          createHref: null,
          createLabel: null
        }
      } as LearningFlowNode;
    }

    const module = moduleById.get(node.id);
    const openable = module?.status === "open" || module?.status === "done";

    return {
      ...node,
      draggable: false,
      data: {
        ...node.data,
        selectHref: null,
        quickHref: null,
        editorHref: null,
        createHref: null,
        createLabel: null,
        connectable: false,
        status: module?.status ?? "locked",
        progressLabel: `${module?.tasks_done ?? 0}/${module?.tasks_total ?? 0} Aufgaben`,
        materialsLabel: `${module?.materials_count ?? 0} Materialien`,
        openable,
        onSelect: openable && module ? () => onOpenModule(module.id) : null
      },
      class: [
        node.class,
        module ? `learning-flow-node--${module.status}` : ""
      ]
        .filter(Boolean)
        .join(" ")
    } as LearningFlowNode;
  });

  const edges = flow.edges.map((edge) => ({
    ...edge,
    selectable: false,
    focusable: false,
    selected: false
  }));

  return { nodes, edges };
}
