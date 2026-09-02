export type SubmissionDraftMode = "text" | "upload";

export type SubmissionDraftScope = {
  learnerSub: string | null;
  courseId: string;
  taskId: string;
  mode: SubmissionDraftMode;
};

/**
 * Builds the browser-storage key for one learner's answer to one task.
 *
 * Returning `null` without an authenticated learner prevents drafts from
 * accidentally sharing an anonymous storage namespace.
 */
export function submissionDraftStorageKey(scope: SubmissionDraftScope): string | null {
  if (!scope.learnerSub) {
    return null;
  }
  return `gustav.learning.submission-draft:${encodeURIComponent(scope.learnerSub)}:${scope.courseId}:${scope.taskId}:${scope.mode}`;
}

export function legacySubmissionDraftStorageKey(scope: Omit<SubmissionDraftScope, "learnerSub">): string {
  return `gustav.learning.submission-draft:${scope.courseId}:${scope.taskId}:${scope.mode}`;
}
