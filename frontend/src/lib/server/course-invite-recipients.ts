/**
 * Convert the teacher-facing multi-address field into the OpenAPI transport shape.
 *
 * Validation, normalization and deduplication intentionally remain in the backend,
 * where every API client receives the same security checks.
 */
export function splitCourseInviteRecipients(value: string): string[] {
  return value
    .split(/[\n,;]/)
    .map((recipient) => recipient.trim())
    .filter(Boolean);
}
