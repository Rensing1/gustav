import type { TeacherUnitWorkspaceView } from "$lib/types/home";

export type GraphDeletionTarget = {
  kind: "phase" | "module";
  id: string;
};

export type GraphDeletionImpact = GraphDeletionTarget & {
  title: string;
  modulesCount: number;
  materialsCount: number;
  tasksCount: number;
  connectionsCount: number;
};

export function graphDeletionImpact(
  workspace: TeacherUnitWorkspaceView,
  target: GraphDeletionTarget
): GraphDeletionImpact | null {
  if (workspace.graph.kind !== "modular") {
    return null;
  }

  const phases = workspace.graph.phases ?? [];
  const edges = workspace.graph.edges ?? [];

  if (target.kind === "module") {
    const module = phases.flatMap((phase) => phase.modules).find((candidate) => candidate.id === target.id);
    if (!module) {
      return null;
    }
    return {
      ...target,
      title: module.title,
      modulesCount: 1,
      materialsCount: module.materials_count,
      tasksCount: module.tasks_count,
      connectionsCount: edges.filter((edge) => edge.from === module.id || edge.to === module.id).length
    };
  }

  const phase = phases.find((candidate) => candidate.id === target.id);
  if (!phase) {
    return null;
  }
  const moduleIds = new Set(phase.modules.map((module) => module.id));
  return {
    ...target,
    title: phase.title,
    modulesCount: phase.modules.length,
    materialsCount: phase.modules.reduce((total, module) => total + module.materials_count, 0),
    tasksCount: phase.modules.reduce((total, module) => total + module.tasks_count, 0),
    connectionsCount: edges.filter((edge) => moduleIds.has(edge.from) || moduleIds.has(edge.to)).length
  };
}

export function graphDeletionFallback(
  workspace: TeacherUnitWorkspaceView,
  target: GraphDeletionTarget
): GraphDeletionTarget | null {
  if (workspace.graph.kind !== "modular") {
    return null;
  }
  const phases = workspace.graph.phases ?? [];

  if (target.kind === "phase") {
    const index = phases.findIndex((phase) => phase.id === target.id);
    const neighbour = index >= 0 ? phases[index + 1] ?? phases[index - 1] : null;
    return neighbour ? { kind: "phase", id: neighbour.id } : null;
  }

  for (const phase of phases) {
    const index = phase.modules.findIndex((module) => module.id === target.id);
    if (index < 0) continue;
    const neighbour = phase.modules[index + 1] ?? phase.modules[index - 1];
    return neighbour
      ? { kind: "module", id: neighbour.id }
      : { kind: "phase", id: phase.id };
  }
  return null;
}
