import { fail, redirect } from "@sveltejs/kit";
import { randomUUID } from "node:crypto";
import type { Actions, PageServerLoad } from "./$types";

import {
  backendRequest,
  requireBackendJson,
  readTypedJsonOrNull
} from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearningPracticeAttempt, LearningPracticeSession, LearningPracticeStack } from "$lib/types/practice";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  const bootstrap = await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");
  const breadcrumbs = [{ label: "Lernraum", href: "/learning" }, { label: "Üben" }];
  const activeSession = await readTypedJsonOrNull<LearningPracticeSession>(
    fetch,
    cookies,
    "/api/learning/practice/sessions/active"
  );
  if (!bootstrap.practice_enabled && !activeSession) {
    return {
      breadcrumbs,
      hidePageHeading: true,
      pageTitle: "Üben",
      enabled: false,
      stacks: [] as LearningPracticeStack[],
      activeSession: null as LearningPracticeSession | null,
      attempt: null as LearningPracticeAttempt | null,
      attemptKey: randomUUID()
    };
  }

  const stackResponse = bootstrap.practice_enabled
    ? await requireBackendJson<{ stacks: LearningPracticeStack[] }>(
      fetch,
      cookies,
      "/api/learning/practice/stacks",
      { authRedirectPath }
    )
    : { stacks: [] as LearningPracticeStack[] };
  const attemptId = url.searchParams.get("attempt_id");
  const attempt = attemptId
    ? await readTypedJsonOrNull<LearningPracticeAttempt>(
        fetch,
        cookies,
        `/api/learning/practice/attempts/${encodeURIComponent(attemptId)}`
      )
    : null;
  const requestedStack = `${url.searchParams.get("course_id") ?? ""}:${url.searchParams.get("practice_module_id") ?? ""}`;
  const selectedStack = stackResponse.stacks.some(
    (stack) => `${stack.course_id}:${stack.practice_module_id}` === requestedStack
  ) ? requestedStack : null;
  return {
    breadcrumbs,
    hidePageHeading: true,
    pageTitle: "Üben",
    enabled: true,
    stacks: stackResponse.stacks,
    selectedStack,
    activeSession,
    attempt,
    attemptKey: randomUUID()
  };
};

async function mutate(
  event: Parameters<NonNullable<Actions[string]>>[0],
  path: string,
  body?: object
) {
  const response = await backendRequest(event.fetch, event.cookies, path, {
    method: "POST",
    authRedirectPath: currentPath(event.url),
    includeSameOrigin: true,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    let detail = "practice_request_failed";
    try {
      detail = String(((await response.json()) as { detail?: string }).detail ?? detail);
    } catch {
      // The status remains sufficient when an upstream proxy returned no JSON.
    }
    return fail(response.status, { practice: { error: detail } });
  }
  throw redirect(303, "/learning/practice");
}

export const actions: Actions = {
  start: async (event) => {
    const form = await event.request.formData();
    const mode = String(form.get("mode") ?? "due");
    const stacks = form.getAll("stack").map((value) => {
      const [course_id, practice_module_id] = String(value).split(":", 2);
      return { course_id, practice_module_id };
    });
    if (!stacks.length) {
      return fail(400, { practice: { error: "Bitte wähle mindestens einen Übungsstapel aus." } });
    }
    return await mutate(event, "/api/learning/practice/sessions", { mode, stacks });
  },
  skip: async (event) => {
    const form = await event.request.formData();
    const sessionId = String(form.get("session_id") ?? "");
    const itemId = String(form.get("item_id") ?? "");
    return await mutate(
      event,
      `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/skip`
    );
  },
  attempt: async (event) => {
    const form = await event.request.formData();
    const sessionId = String(form.get("session_id") ?? "");
    const itemId = String(form.get("item_id") ?? "");
    const answerText = String(form.get("answer_text") ?? "").trim();
    const idempotencyKey = String(form.get("idempotency_key") ?? "").trim();
    if (!answerText || !idempotencyKey) {
      return fail(400, { practice: { error: "Bitte gib eine Antwort ein." } });
    }
    const response = await backendRequest(
      event.fetch,
      event.cookies,
      `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/attempts`,
      {
        method: "POST",
        authRedirectPath: currentPath(event.url),
        includeSameOrigin: true,
        headers: { "content-type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ answer_text: answerText })
      }
    );
    if (!response.ok) {
      const error = (await readErrorDetail(response)) ?? "practice_request_failed";
      return fail(response.status, { practice: { error } });
    }
    const accepted = (await response.json()) as { attempt_id: string };
    throw redirect(303, `/learning/practice?attempt_id=${encodeURIComponent(accepted.attempt_id)}`);
  },
  solution: async (event) => {
    const form = await event.request.formData();
    const sessionId = String(form.get("session_id") ?? "");
    const itemId = String(form.get("item_id") ?? "");
    const response = await backendRequest(
      event.fetch,
      event.cookies,
      `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/solution`,
      { method: "POST", authRedirectPath: currentPath(event.url), includeSameOrigin: true }
    );
    if (!response.ok) {
      const error = (await readErrorDetail(response)) ?? "practice_request_failed";
      return fail(response.status, { practice: { error } });
    }
    const solution = (await response.json()) as { model_solution_md: string };
    return { practice: { solution: solution.model_solution_md } };
  },
  continue: async (event) => {
    const form = await event.request.formData();
    const sessionId = String(form.get("session_id") ?? "");
    return await mutate(
      event,
      `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/continue`
    );
  },
  end: async (event) => {
    const form = await event.request.formData();
    const sessionId = String(form.get("session_id") ?? "");
    return await mutate(
      event,
      `/api/learning/practice/sessions/${encodeURIComponent(sessionId)}/end`
    );
  }
};

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    return String(((await response.json()) as { detail?: string }).detail ?? "") || null;
  } catch {
    return null;
  }
}
