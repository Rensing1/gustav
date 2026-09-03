import type { LearningSubmission, LearningTask } from "$lib/types/learning";
import type { LearnerNavigationTarget } from "$lib/learning-unit/learner-navigation";

export type LearnerReturnDestination = "module" | "learningPath" | "contents";

type LearnerReturnPosition = {
  moduleId: string | null;
  scrollY: number;
  focusId: string | null;
};

type LearnerReturnNavigation = {
  target: LearnerNavigationTarget;
  restorablePosition: LearnerReturnPosition | null;
};

type CompletionReturnInput = {
  unitType: "linear" | "modular";
  currentTaskId: string;
  moduleTasks: LearningTask[];
  historyByTask: Record<string, LearningSubmission[]>;
};

function isFinallySubmitted(
  task: LearningTask,
  history: LearningSubmission[] | undefined
): boolean {
  return Boolean(
    task.latest_final_submission_at ||
      history?.some((submission) => submission.intent === "submit")
  );
}

/**
 * Choose the safe destination after a final task submission.
 *
 * A modular learner should review the module while any other task is still
 * open. Missing completion data is therefore treated conservatively as open.
 */
export function completionReturnDestination({
  unitType,
  currentTaskId,
  moduleTasks,
  historyByTask
}: CompletionReturnInput): LearnerReturnDestination {
  if (unitType === "linear") {
    return "contents";
  }

  const hasAnotherOpenTask = moduleTasks.some(
    (task) => task.id !== currentTaskId && !isFinallySubmitted(task, historyByTask[task.id])
  );
  return hasAnotherOpenTask ? "module" : "learningPath";
}

export function learnerReturnLabel(destination: LearnerReturnDestination): string {
  if (destination === "module") {
    return "Zurück zum Modul";
  }
  if (destination === "contents") {
    return "Zurück zu den Inhalten";
  }
  return "Zurück zum Lernpfad";
}

/**
 * Resolve the visible return target and any position that safely belongs to it.
 *
 * The active task is the source of truth for its module. A stored position is
 * only navigation fallback when no task is active, and is never restored in a
 * different module.
 */
export function resolveLearnerReturnNavigation({
  destination,
  activeTaskModuleId,
  returnPosition
}: {
  destination: LearnerReturnDestination;
  activeTaskModuleId: string | null;
  returnPosition: LearnerReturnPosition | null;
}): LearnerReturnNavigation {
  const moduleId = activeTaskModuleId ?? returnPosition?.moduleId ?? null;
  const target: LearnerNavigationTarget = destination === "learningPath" ||
    (destination === "module" && !moduleId)
    ? { surface: "graph", moduleId: null, taskId: null, panel: null }
    : {
        surface: "reading",
        moduleId: destination === "module" ? moduleId : null,
        taskId: null,
        panel: null
      };
  const restorablePosition = target.surface === "reading" &&
    returnPosition?.moduleId === target.moduleId
    ? returnPosition
    : null;

  return { target, restorablePosition };
}
