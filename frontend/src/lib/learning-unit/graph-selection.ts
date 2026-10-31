import type { LearningUnitGraphModule } from "$lib/types/learning";

type LearnerFocusNode = {
  id: string;
  type?: string;
  selected?: boolean;
  data: { status?: LearningUnitGraphModule["status"] };
};

/**
 * Choose a readable learner entry point without changing graph order or access.
 * Narrow screens focus a module instead of a potentially very wide phase.
 * Nodes must come from the authorized learner graph; this only chooses a camera
 * target and never opens content. Empty graphs have no focus target.
 */
export function learnerGraphFocusId(nodes: LearnerFocusNode[], compact: boolean): string | null {
  const modules = nodes.filter((node) => node.type === "unitNode");
  const selected = modules.find((node) => node.selected);
  const compactTarget = compact
    ? modules.find((node) => node.data.status === "open") ?? modules[0]
    : undefined;
  return (selected ?? compactTarget ?? nodes.find((node) => node.type === "phaseBand"))?.id ?? null;
}

/**
 * Returns the learner module ids that should stay highlighted in the graph.
 *
 * Learners may keep multiple modules open at the same time. The graph mirrors
 * that workspace state directly instead of collapsing it to a single selection.
 */
export function highlightedLearnerGraphModuleIds(openTabs: string[]): string[] {
  return Array.from(new Set(openTabs));
}

/**
 * Returns whether a learner node should use the orange "working" highlight.
 *
 * Only unfinished, currently open modules receive the orange state. Finished
 * modules keep their green status styling even when they remain open.
 */
export function learnerGraphNodeIsSelected(
  status: LearningUnitGraphModule["status"] | undefined,
  openModuleIds: Set<string>,
  moduleId: string
): boolean {
  return status === "open" && openModuleIds.has(moduleId);
}
