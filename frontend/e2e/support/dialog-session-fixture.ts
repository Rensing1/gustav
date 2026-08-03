import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { e2eDatabaseUrl } from "./e2e-env";

const execFileAsync = promisify(execFile);
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const subjectPattern = /^[A-Za-z0-9_-]{1,128}$/;

function validatedUuid(value: string, label: string): string {
  if (!uuidPattern.test(value)) throw new Error(`Invalid ${label} for dialog fixture`);
  return value;
}

function validatedSubject(value: string): string {
  if (!subjectPattern.test(value)) throw new Error("Invalid learner subject for dialog fixture");
  return value;
}

/**
 * Prepare one completed turn without contacting the configured AI provider.
 *
 * The session itself must already exist through the real learner endpoint. The
 * fixture only replaces the external provider step and keeps all following UI,
 * API, RLS-facing reads and final submission behavior production-like.
 */
export async function prepareCompletedDialogTurn(input: {
  courseId: string;
  taskId: string;
  learnerSub: string;
}): Promise<string> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for dialog feature acceptance");
  }
  const courseId = validatedUuid(input.courseId, "course id");
  const taskId = validatedUuid(input.taskId, "task id");
  const learnerSub = validatedSubject(input.learnerSub);
  const sql = `
    with target as (
      select id
        from public.learning_dialog_sessions
       where course_id = '${courseId}'::uuid
         and task_id = '${taskId}'::uuid
         and student_sub = '${learnerSub}'
         and status = 'active'
       order by created_at desc
       limit 1
    ), inserted as (
      insert into public.learning_dialog_turns (
        session_id, round_nr, student_message_md, status,
        assistant_reply_md, sentence_starters, generation_attempts,
        idempotency_key, generation_started_at, completed_at
      )
      select id, 1, 'Die Quelle betont nur eine Perspektive.', 'completed',
             'Welche Textstelle belegt diese Beobachtung?', '{}', 1,
             'e2e-dialog-turn-1', now(), now()
        from target
      returning session_id
    ), updated as (
      update public.learning_dialog_sessions as session
         set round_count = 1
       where session.id = (select session_id from inserted)
      returning session.id
    )
    select id from updated;
  `;
  const { stdout } = await execFileAsync("psql", [e2eDatabaseUrl, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024
  });
  const sessionId = stdout.trim();
  if (!uuidPattern.test(sessionId)) {
    throw new Error("The learner dialog session was not available for deterministic preparation");
  }
  return sessionId;
}
