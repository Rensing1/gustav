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
  longTranscript?: boolean;
}): Promise<string> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for dialog feature acceptance");
  }
  const courseId = validatedUuid(input.courseId, "course id");
  const taskId = validatedUuid(input.taskId, "task id");
  const learnerSub = validatedSubject(input.learnerSub);
  const studentMessage = input.longTranscript
    ? [
        "Die Quelle betont nur eine Perspektive.",
        "Prüfe zunächst, wer die Aussage formuliert und welches Interesse damit verbunden sein könnte.",
        "Unterscheide anschließend zwischen einer Beobachtung im Material und deiner eigenen Bewertung.",
        "Achte außerdem darauf, welche Gegenposition oder welche zusätzlichen Daten für eine sichere Einordnung fehlen.",
        "Notiere, welche Begriffe besonders wertend formuliert sind und welche Wirkung diese Wortwahl auf Leserinnen und Leser haben kann.",
        "Vergleiche danach Überschrift, Einleitung und Schluss: Unterstützen alle drei Teile dieselbe Perspektive oder entstehen Widersprüche?",
        "Prüfe auch, ob Zahlen oder Beispiele genannt werden und ob ihre Herkunft so beschrieben ist, dass du sie nachvollziehen kannst.",
        "Eine zuverlässige Begründung trennt klar zwischen dem sichtbaren Beleg, deiner Schlussfolgerung und einer noch offenen Frage.",
        "Überlege, welche Information deine Einschätzung widerlegen könnte. So vermeidest du, nur nach bestätigenden Hinweisen zu suchen.",
        "Wenn eine Person oder Institution zitiert wird, prüfe, ob ihre Rolle und ihr möglicher Standpunkt im Material verständlich werden.",
        "Formuliere deine Beobachtung anschließend in einem Satz, der ohne pauschale Behauptung auskommt und auf einen konkreten Beleg verweist.",
        "Du kannst dabei benennen, was das Material zeigt, was es nicht zeigt und weshalb diese Lücke für die Einordnung wichtig ist.",
        "Wähle nun den stärksten Beleg aus dem Material, statt mehrere nur lose passende Stellen aufzuzählen."
      ].join("\n\n")
    : "Die Quelle betont nur eine Perspektive.";
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
      select id, 1, '${studentMessage}', 'completed',
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

/** Append a terminal provider failure after an already completed dialog round. */
export async function appendTerminalDialogFailure(sessionIdInput: string): Promise<void> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for dialog feature acceptance");
  }
  const sessionId = validatedUuid(sessionIdInput, "session id");
  const sql = `
    insert into public.learning_dialog_turns (
      session_id, round_nr, student_message_md, status,
      sentence_starters, generation_attempts, error_code,
      idempotency_key, generation_started_at
    ) values (
      '${sessionId}'::uuid, 2, 'Eine zweite Beobachtung.', 'failed',
      '{}', 3, 'dialog_ai_unavailable',
      'e2e-dialog-turn-2', now()
    );
  `;
  await execFileAsync("psql", [e2eDatabaseUrl, "-X", "-v", "ON_ERROR_STOP=1", "-c", sql], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024
  });
}

/**
 * Complete the feedback for one isolated dialog submission deterministically.
 *
 * The browser still creates the session, final submission and queue job through
 * production endpoints. This fixture replaces only the external AI provider so
 * the acceptance test can verify the pending-to-visible-feedback transition.
 */
export async function completeDialogFeedback(input: {
  sessionId: string;
  feedbackMd: string;
}): Promise<string> {
  if (!e2eDatabaseUrl) {
    throw new Error("E2E_DATABASE_URL or SESSION_DATABASE_URL is required for dialog feature acceptance");
  }
  const sessionId = validatedUuid(input.sessionId, "session id");
  const feedbackMd = input.feedbackMd.replaceAll("'", "''");
  const sql = `
    delete from public.learning_submission_jobs
     where submission_id = (
       select id from public.learning_submissions
        where dialog_session_id = '${sessionId}'::uuid
     );

    update public.learning_submissions
       set analysis_status = 'completed',
           analysis_json = '{"schema":"criteria.v2","criteria_results":[]}'::jsonb,
           feedback_md = '${feedbackMd}',
           completed_at = now(),
           error_code = null
     where dialog_session_id = '${sessionId}'::uuid
     returning id;
  `;
  const { stdout } = await execFileAsync(
    "psql",
    [e2eDatabaseUrl, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
    { encoding: "utf8", maxBuffer: 1024 * 1024 }
  );
  const submissionId = stdout.split("\n").map((line) => line.trim()).find((line) => uuidPattern.test(line)) ?? "";
  if (!uuidPattern.test(submissionId)) {
    throw new Error("The final dialog submission was not available for deterministic feedback");
  }
  return submissionId;
}
