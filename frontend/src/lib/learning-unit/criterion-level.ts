import type { LearningSubmission } from "$lib/types/learning";

export type LearningCriterionResult = NonNullable<
  NonNullable<LearningSubmission["analysis_json"]>["criteria_results"]
>[number];

export type CriterionLevel = "Mangelhaft" | "Ansatzweise" | "Gelungen" | "Hervorragend" | "Ohne Einstufung";

/**
 * Convert a criterion score to GUSTAV's common ten-point comparison scale.
 * Invalid values deliberately stay unclassified instead of presenting a
 * misleading learner-facing judgement.
 */
export function normalizedCriterionScore(
  score: number | null | undefined,
  maxScore: number | null | undefined
): number | null {
  const effectiveMaximum = maxScore ?? 10;
  if (
    typeof score !== "number" ||
    !Number.isFinite(score) ||
    !Number.isFinite(effectiveMaximum) ||
    effectiveMaximum <= 0 ||
    score < 0 ||
    score > effectiveMaximum
  ) {
    return null;
  }
  return (score / effectiveMaximum) * 10;
}

/** Describe criterion fulfilment without exposing the stored numeric score. */
export function criterionLevel(
  score: number | null | undefined,
  maxScore: number | null | undefined
): CriterionLevel {
  const normalized = normalizedCriterionScore(score, maxScore);
  if (normalized === null) return "Ohne Einstufung";
  if (normalized <= 2) return "Mangelhaft";
  if (normalized <= 6) return "Ansatzweise";
  if (normalized <= 8) return "Gelungen";
  return "Hervorragend";
}
