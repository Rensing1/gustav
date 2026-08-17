import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promisify } from "node:util";

import { e2eDatabaseUrl } from "./e2e-env";

const execFileAsync = promisify(execFile);
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const subjectPattern = /^[A-Za-z0-9_-]{1,128}$/;

function validatedUuid(value: string, label: string): string {
  if (!uuidPattern.test(value)) throw new Error(`Invalid ${label} for finalization fixture`);
  return value;
}

function validatedSubject(value: string): string {
  if (!subjectPattern.test(value)) throw new Error("Invalid learner subject for finalization fixture");
  return value;
}

/**
 * Inserts an already reviewed draft so the browser test exercises finalization
 * without depending on an external AI provider.
 */
type CompletedFeedbackDraftInput = {
  courseId: string;
  taskId: string;
  learnerSub: string;
} & (
  | { kind?: "text"; textBody: string }
  | { kind: "file"; textBody?: never }
);

export async function prepareCompletedFeedbackDraft(input: CompletedFeedbackDraftInput): Promise<void> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for submission finalization acceptance");
  }
  const courseId = validatedUuid(input.courseId, "course id");
  const taskId = validatedUuid(input.taskId, "task id");
  const learnerSub = validatedSubject(input.learnerSub);
  const submissionId = randomUUID();
  const isFile = input.kind === "file";
  const kind = isFile ? "file" : "text";
  const textBody = isFile ? "null" : `'${input.textBody.replaceAll("'", "''")}'`;
  const storageKey = isFile
    ? `'submissions/${courseId}/${taskId}/${learnerSub}/${submissionId}.pdf'`
    : "null";
  const mimeType = isFile ? "'application/pdf'" : "null";
  const sizeBytes = isFile ? "128" : "null";
  const sha256 = isFile ? `'${"0".repeat(64)}'` : "null";
  const sql = `
    insert into public.learning_submissions (
      id, course_id, task_id, section_id, student_sub, intent, kind,
      text_body, storage_key, mime_type, size_bytes, sha256,
      attempt_nr, analysis_status, analysis_json, feedback_md,
      created_at, completed_at
    ) values (
      '${submissionId}'::uuid, '${courseId}'::uuid, '${taskId}'::uuid,
      (select section_id from public.unit_tasks where id = '${taskId}'::uuid),
      '${learnerSub}', 'feedback', '${kind}', ${textBody}, ${storageKey}, ${mimeType}, ${sizeBytes}, ${sha256},
      1, 'completed',
      '{"schema":"criteria.v2","criteria_results":[]}'::jsonb,
      'Die Fassung wurde geprüft und kann endgültig abgegeben werden.',
      now(), now()
    );
    select 1;
  `;
  const { stdout } = await execFileAsync(
    "psql",
    [e2eDatabaseUrl, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
    { encoding: "utf8", maxBuffer: 1024 * 1024 }
  );
  if (!stdout.trim().endsWith("1")) {
    throw new Error("Completed feedback draft could not be prepared");
  }
}
