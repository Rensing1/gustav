export type SubmissionDraftMode = "text" | "upload";

export type SubmissionDraftScope = {
  learnerSub: string | null;
  courseId: string;
  taskId: string;
  mode: SubmissionDraftMode;
};

export type SubmissionDraftStorage = Pick<Storage, "getItem" | "removeItem" | "setItem">;

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

/** Removes only the draft keys that belong to the supplied course and task. */
export function clearSubmissionDraft(storage: SubmissionDraftStorage, scope: SubmissionDraftScope): void {
  const scopedKey = submissionDraftStorageKey(scope);
  if (scopedKey) {
    storage.removeItem(scopedKey);
  }
  storage.removeItem(legacySubmissionDraftStorageKey(scope));
}
