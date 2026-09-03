import type { LearningSubmission, LearningTask } from "$lib/types/learning";

export type LearnerReturnDestination = "module" | "learningPath" | "contents";

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
