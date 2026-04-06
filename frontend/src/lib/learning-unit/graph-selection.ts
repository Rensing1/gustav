import type { LearningUnitGraphModule } from "$lib/types/learning";

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
