import type {
  TeacherUnitWorkspaceEdgeSelection,
  TeacherUnitWorkspaceGraphPhase,
  TeacherUnitWorkspaceModuleItem,
  TeacherUnitWorkspaceSectionItem,
  TeacherUnitWorkspaceSelection,
  TeacherUnitWorkspaceView
} from "$lib/types/home";


export function cloneWorkspace(workspace: TeacherUnitWorkspaceView): TeacherUnitWorkspaceView {
  return JSON.parse(JSON.stringify(workspace)) as TeacherUnitWorkspaceView;
}


export function workspaceGraphSignature(workspace: TeacherUnitWorkspaceView): string {
  if (workspace.graph.kind === "linear") {
    return JSON.stringify({
      unit: workspace.unit.id,
      kind: workspace.graph.kind,
      sections: (workspace.graph.nodes ?? []).map((section) => [
        section.id,
        section.title,
        section.position
      ]),
      edges: workspace.graph.edges
    });
  }

  return JSON.stringify({
    unit: workspace.unit.id,
    kind: workspace.graph.kind,
    phases: (workspace.graph.phases ?? []).map((phase) => [
      phase.id,
      phase.title,
      phase.position,
      phase.modules.map((module) => [
        module.id,
        module.title,
        module.phase_id,
        module.position_in_phase,
        module.required_prereq_count
      ])
    ]),
    edges: workspace.graph.edges
  });
}


export function modularPhases(
  workspace: TeacherUnitWorkspaceView
): TeacherUnitWorkspaceGraphPhase[] {
  return workspace.graph.kind === "modular" ? (workspace.graph.phases ?? []) : [];
}


export function graphSections(
  workspace: TeacherUnitWorkspaceView
): TeacherUnitWorkspaceSectionItem[] {
  return workspace.graph.kind === "linear" ? (workspace.graph.nodes ?? []) : [];
}


export function allModules(workspace: TeacherUnitWorkspaceView): TeacherUnitWorkspaceModuleItem[] {
  return modularPhases(workspace).flatMap((phase) => phase.modules);
}


export function findPhaseById(
  workspace: TeacherUnitWorkspaceView,
  phaseId: string
): TeacherUnitWorkspaceGraphPhase | null {
  return modularPhases(workspace).find((phase) => phase.id === phaseId) ?? null;
}


export function findModuleById(
  workspace: TeacherUnitWorkspaceView,
  moduleId: string
): TeacherUnitWorkspaceModuleItem | null {
  return allModules(workspace).find((module) => module.id === moduleId) ?? null;
}


export function findSectionById(
  workspace: TeacherUnitWorkspaceView,
  sectionId: string
): TeacherUnitWorkspaceSectionItem | null {
  return graphSections(workspace).find((section) => section.id === sectionId) ?? null;
}


export function edgeExists(
  workspace: TeacherUnitWorkspaceView,
  fromId: string,
  toId: string
): boolean {
  return (workspace.graph.edges ?? []).some((edge) => edge.from === fromId && edge.to === toId);
}


export function deriveSectionSelection(
  workspace: TeacherUnitWorkspaceView,
  sectionId: string
): TeacherUnitWorkspaceSelection {
  const section = findSectionById(workspace, sectionId);
  if (!section) {
    return { kind: "none" };
  }
  return {
    kind: "section",
    section: {
      id: section.id,
      title: section.title,
      position: section.position,
      editor_href: section.editor_href
    }
  };
}


export function derivePhaseSelection(
  workspace: TeacherUnitWorkspaceView,
  phaseId: string
): TeacherUnitWorkspaceSelection {
  const phase = findPhaseById(workspace, phaseId);
  if (!phase) {
    return { kind: "none" };
  }
  return {
    kind: "phase",
    phase: {
      id: phase.id,
      title: phase.title,
      position: phase.position
    }
  };
}


export function deriveModuleSelection(
  workspace: TeacherUnitWorkspaceView,
  moduleId: string
): TeacherUnitWorkspaceSelection {
  const module = findModuleById(workspace, moduleId);
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
      module_kind: module.module_kind,
      required_prereq_count: module.required_prereq_count,
      materials_count: module.materials_count,
      tasks_count: module.tasks_count,
      editor_href: module.editor_href
    }
  };
}


export function deriveEdgeSelection(
  workspace: TeacherUnitWorkspaceView,
  fromId: string,
  toId: string
): TeacherUnitWorkspaceSelection {
  const fromModule = findModuleById(workspace, fromId);
  const toModule = findModuleById(workspace, toId);
  if (!fromModule || !toModule) {
    return { kind: "none" };
  }

  const edge: TeacherUnitWorkspaceEdgeSelection = {
    from_id: fromModule.id,
    to_id: toModule.id,
    from_title: fromModule.title,
    to_title: toModule.title,
    exists: edgeExists(workspace, fromId, toId)
  };
  return { kind: "edge", edge };
}
