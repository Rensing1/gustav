import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promisify } from "node:util";

import { e2eDatabaseUrl } from "./e2e-env";

const execFileAsync = promisify(execFile);
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const subjectPattern = /^[A-Za-z0-9_-]{1,128}$/;

function validatedUuid(value: string, label: string): string {
  if (!uuidPattern.test(value)) throw new Error(`Invalid ${label} for AI usage fixture`);
  return value;
}

function validatedSubject(value: string): string {
  if (!subjectPattern.test(value)) throw new Error("Invalid learner subject for AI usage fixture");
  return value;
}

/**
 * Seed deterministic provider telemetry without contacting an external LLM.
 *
 * Course, unit, task and membership already exist through the real APIs. This
 * helper only replaces the costly provider calls while retaining production
 * tables, foreign keys, RLS-facing reads and the browser-to-backend journey.
 */
export async function prepareCourseAiUsage(input: {
  courseId: string;
  unitId: string;
  taskId: string;
  learnerSub: string;
}): Promise<void> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for AI usage feature acceptance");
  }

  const courseId = validatedUuid(input.courseId, "course id");
  const unitId = validatedUuid(input.unitId, "unit id");
  const taskId = validatedUuid(input.taskId, "task id");
  const learnerSub = validatedSubject(input.learnerSub);
  const submissionId = randomUUID();
  const sessionId = randomUUID();
  const sql = `
    insert into public.learning_submissions (
      id, course_id, task_id, section_id, student_sub, kind, text_body,
      attempt_nr, analysis_status, created_at
    ) values (
      '${submissionId}'::uuid, '${courseId}'::uuid, '${taskId}'::uuid,
      (select section_id from public.unit_tasks where id = '${taskId}'::uuid),
      '${learnerSub}', 'text', 'Deterministische E2E-Abgabe', 1, 'completed',
      '2026-08-08 10:00:00+00'
    );

    insert into public.ai_usage_events (
      event_key, occurred_at, submission_id, course_id, unit_id, task_id,
      student_sub, model, stage, modality, call_kind, usage_known,
      input_tokens, output_tokens, total_tokens
    ) values (
      '${randomUUID()}'::uuid, '2026-08-08 10:00:00+00', '${submissionId}'::uuid,
      '${courseId}'::uuid, '${unitId}'::uuid, '${taskId}'::uuid, '${learnerSub}',
      'model-submission', 'feedback', 'text', 'primary', true, 1200, 300, 1500
    );

    insert into public.learning_dialog_sessions (id, course_id, task_id, student_sub)
    values ('${sessionId}'::uuid, '${courseId}'::uuid, '${taskId}'::uuid, '${learnerSub}');

    insert into public.dialog_ai_usage_events (
      event_key, occurred_at, session_id, course_id, unit_id, task_id,
      actor_sub, actor_role, stage, model, usage_known,
      input_tokens, output_tokens, total_tokens, unknown_reason
    ) values
      (
        '${randomUUID()}'::uuid, '2026-08-07 10:00:00+00', '${sessionId}'::uuid,
        '${courseId}'::uuid, '${unitId}'::uuid, '${taskId}'::uuid, '${learnerSub}',
        'student', 'initial_starters', 'model-dialog', true, 400, 100, 500, null
      ),
      (
        '${randomUUID()}'::uuid, '2026-08-07 10:05:00+00', '${sessionId}'::uuid,
        '${courseId}'::uuid, '${unitId}'::uuid, '${taskId}'::uuid, '${learnerSub}',
        'student', 'reply', 'model-dialog', false, null, null, null, 'missing_provider_usage'
      );

    select 1;
  `;
  const { stdout } = await execFileAsync(
    "psql",
    [e2eDatabaseUrl, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
    { encoding: "utf8", maxBuffer: 1024 * 1024 }
  );
  if (!stdout.trim().endsWith("1")) {
    throw new Error("Deterministic AI usage telemetry could not be prepared");
  }
}
