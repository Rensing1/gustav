import { fail, redirect } from "@sveltejs/kit";
import { randomUUID } from "node:crypto";
import type { Actions, PageServerLoad } from "./$types";

import {
  backendRequest,
  requireBackendJson,
  readTypedJsonOrNull
} from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearningPracticeAttempt, LearningPracticeSession, LearningPracticeStack, LearningPracticeStackSelection } from "$lib/types/practice";
import { practiceActionUrls, practiceErrorMessage } from "$lib/practice/practice-presentation";

function moduleContext(url: URL) {
  const courseId = url.searchParams.get("course_id");
  const moduleId = url.searchParams.get("practice_module_id");
  if (courseId === null && moduleId === null) return null;

  const query = new URLSearchParams();
  if (courseId !== null) query.set("course_id", courseId);
  if (moduleId !== null) query.set("practice_module_id", moduleId);
  return {
    query: query.toString(),
    selection: courseId && moduleId ? { course_id: courseId, practice_module_id: moduleId } : null
  };
}

function sameStack(stack: LearningPracticeStackSelection, other: LearningPracticeStackSelection | null) {
  return stack.course_id === other?.course_id && stack.practice_module_id === other.practice_module_id;
}

function practicePageUrl(url: URL) {
  const context = moduleContext(url);
  return context ? `/learning/practice?${context.query}` : "/learning/practice";
}

export const load = (async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");
  let breadcrumbs = [{ label: "Lernraum", href: "/learning" }, { label: "Üben" }];
  const session = await readTypedJsonOrNull<LearningPracticeSession>(
    fetch,
    cookies,
    "/api/learning/practice/sessions/active"
  );
  const stackResponse = await requireBackendJson<{ stacks: LearningPracticeStack[] }>(
      fetch,
      cookies,
      "/api/learning/practice/stacks",
      { authRedirectPath }
    );
  const context = moduleContext(url);
  const requestedStack = context
    ? stackResponse.stacks.find(stack => sameStack(stack, context.selection))
    : undefined;
  const matchesContext = session?.stacks?.length === 1 && context && sameStack(session.stacks[0], context.selection);
  // An empty matching session still needs its existing exit after task removal.
  const activeSession = context && !(matchesContext && (requestedStack || !session?.current_item))
    ? null
    : session;
  const attemptId = activeSession?.current_item?.latest_attempt_id;
  const attempt = attemptId
    ? await readTypedJsonOrNull<LearningPracticeAttempt>(
        fetch,
        cookies,
        `/api/learning/practice/attempts/${encodeURIComponent(attemptId)}`
      )
    : null;
  const currentItem = activeSession?.current_item;
  const contextStack = context
    ? requestedStack
    : currentItem && stackResponse.stacks.find(stack => sameStack(stack, currentItem));
  if (contextStack) {
    const courseHref = `/learning/courses/${encodeURIComponent(contextStack.course_id)}`;
    breadcrumbs = [
      { label: "Lernraum", href: "/learning" },
      { label: contextStack.course_title, href: courseHref },
      { label: contextStack.unit_title, href: `${courseHref}/units/${encodeURIComponent(contextStack.unit_id)}` },
      { label: contextStack.module_title }
    ];
  }
  const selectedMode: "due" | "exam" = url.searchParams.get("mode") === "exam" ? "exam" : "due";
  return {
    breadcrumbs,
    hidePageHeading: true,
    pageTitle: "Üben",
    stacks: context ? (requestedStack ? [requestedStack] : []) : stackResponse.stacks,
    moduleScoped: context !== null,
    actionUrls: practiceActionUrls(context?.query),
    replaceActiveSessionId: requestedStack && !activeSession ? session?.id ?? null : null,
    selectedMode,
    activeSession,
    attempt,
    attemptKey: randomUUID(),
    nowIso: new Date().toISOString()
  };
}) satisfies PageServerLoad;

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
    return fail(response.status, { practice: { error: practiceErrorMessage(detail) } });
  }
  const session = (await response.json()) as LearningPracticeSession;
  const destination = session.status === "ended"
    ? `/learning/practice/sessions/${encodeURIComponent(session.id)}/summary`
    : practicePageUrl(event.url);
  throw redirect(303, destination);
}

export const actions: Actions = {
  start: async (event) => {
    const form = await event.request.formData();
    const mode = String(form.get("mode") ?? "due");
    const context = moduleContext(event.url);
    if (context) {
      if (!context.selection) {
        return fail(404, { practice: { error: "Dieses Übungsmodul ist nicht verfügbar." } });
      }
      return await mutate(event, "/api/learning/practice/sessions", {
        mode,
        stacks: [context.selection],
        replace_active_session_id: form.get("replace_active_session_id") || undefined
      });
    }
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
      return fail(response.status, { practice: { error: practiceErrorMessage(error) } });
    }
    await response.json();
    throw redirect(303, practicePageUrl(event.url));
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
      return fail(response.status, { practice: { error: practiceErrorMessage(error) } });
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
