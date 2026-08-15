import type { LearningPracticeAttempt, LearningPracticeSessionItem } from "$lib/types/practice";

export function practiceSessionNeedsPolling(
  itemStatus: LearningPracticeSessionItem["status"] | null,
  attemptStatus: LearningPracticeAttempt["status"] | null
): boolean {
  return itemStatus === "awaiting_analysis" || attemptStatus === "pending";
}

export function practiceClassificationLabel(
  classification: LearningPracticeAttempt["classification"]
): string {
  if (classification === "secure") return "Sicher beantwortet";
  if (classification === "partial") return "Teilweise beantwortet";
  if (classification === "insufficient") return "Noch nicht sicher";
  return "Rückmeldung";
}

export function practiceDueLabel(dueAt: string | null, nowIso: string): string | null {
  if (!dueAt) return null;
  const dueMs = Date.parse(dueAt);
  const nowMs = Date.parse(nowIso);
  if (!Number.isFinite(dueMs) || !Number.isFinite(nowMs)) return null;

  const remainingDays = Math.ceil((dueMs - nowMs) / 86_400_000);
  if (remainingDays <= 0) return "Jetzt wiederholen";
  if (remainingDays === 1) return "Nächste Wiederholung morgen";
  if (remainingDays < 45) return `Nächste Wiederholung in ${remainingDays} Tagen`;

  const months = Math.ceil(remainingDays / 30);
  if (months === 1) return "Nächste Wiederholung in einem Monat";
  return `Nächste Wiederholung in ${months} Monaten`;
}

export function practiceCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

const PRACTICE_ERROR_MESSAGES: Record<string, string> = {
  invalid_practice_stacks: "Bitte wähle mindestens ein Thema aus.",
  too_many_stacks: "Bitte wähle höchstens 50 Themen aus.",
  session_item_limit_exceeded: "Diese Auswahl enthält zu viele Aufgaben. Bitte wähle weniger Themen aus.",
  practice_stack_not_found: "Mindestens ein ausgewähltes Thema ist nicht mehr verfügbar.",
  practice_session_active: "Du hast bereits eine aktive Übungssitzung.",
  practice_feedback_pending: "Die Rückmeldung ist noch nicht fertig.",
  practice_item_state_conflict: "Diese Aufgabe wurde bereits verarbeitet. Die Seite wird beim nächsten Aufruf aktualisiert.",
  practice_idempotency_conflict: "Diese Abgabe konnte nicht eindeutig zugeordnet werden. Bitte lade die Seite neu.",
  invalid_practice_answer: "Bitte gib eine Antwort ein.",
  practice_request_failed: "Die Aktion konnte nicht abgeschlossen werden. Bitte versuche es erneut."
};

export function practiceErrorMessage(code: string): string {
  return PRACTICE_ERROR_MESSAGES[code] ?? PRACTICE_ERROR_MESSAGES.practice_request_failed;
}
