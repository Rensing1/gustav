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
export async function prepareCompletedFeedbackDraft(input: {
  courseId: string;
  taskId: string;
  learnerSub: string;
  textBody: string;
}): Promise<void> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for submission finalization acceptance");
  }
  const courseId = validatedUuid(input.courseId, "course id");
  const taskId = validatedUuid(input.taskId, "task id");
  const learnerSub = validatedSubject(input.learnerSub);
  const textBody = input.textBody.replaceAll("'", "''");
  const submissionId = randomUUID();
  const sql = `
    insert into public.learning_submissions (
      id, course_id, task_id, section_id, student_sub, intent, kind,
      text_body, attempt_nr, analysis_status, analysis_json, feedback_md,
      created_at, completed_at
    ) values (
      '${submissionId}'::uuid, '${courseId}'::uuid, '${taskId}'::uuid,
      (select section_id from public.unit_tasks where id = '${taskId}'::uuid),
      '${learnerSub}', 'feedback', 'text', '${textBody}', 1, 'completed',
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
