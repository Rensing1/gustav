import type { LearningSubmission } from "$lib/types/learning";

export type H5PPersistedResult =
  | { kind: "learning"; submission: LearningSubmission }
  | { kind: "practice"; attemptId: string; status: string };
