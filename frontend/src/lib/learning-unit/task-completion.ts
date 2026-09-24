import type { LearningSubmission, LearningTask } from "$lib/types/learning";

export type H5PScore = { raw: number; max: number };

function submissionScore(submission: LearningSubmission | undefined): H5PScore | null {
  if (
    submission?.kind !== "h5p" ||
    typeof submission.score_raw !== "number" ||
    typeof submission.score_max !== "number"
  ) {
    return null;
  }
  return { raw: submission.score_raw, max: submission.score_max };
}

export function latestH5PScore(
  task: LearningTask,
  history: LearningSubmission[] = []
): H5PScore | null {
  const historyScore = submissionScore(history.find((submission) => submission.kind === "h5p"));
  if (historyScore) {
    return historyScore;
  }
  if (typeof task.score_raw === "number" && typeof task.score_max === "number") {
    return { raw: task.score_raw, max: task.score_max };
  }
  return null;
}

export function taskIsComplete(
  task: LearningTask,
  history: LearningSubmission[] = []
): boolean {
  if (task.kind === "h5p") {
    return task.h5p_completed === true || history.some((submission) => {
      const score = submissionScore(submission);
      return score !== null && score.raw === score.max;
    });
  }
  return Boolean(
    task.latest_final_submission_at ||
      history.some((submission) => submission.intent === "submit")
  );
}

export function h5pProgressLabel(
  task: LearningTask,
  history: LearningSubmission[] = []
): string {
  const score = latestH5PScore(task, history);
  if (!score) {
    return "Noch nicht bearbeitet";
  }
  const state = taskIsComplete(task, history) ? "Abgeschlossen" : "Noch nicht abgeschlossen";
  return `${state} · zuletzt ${score.raw}/${score.max} Punkte`;
}
