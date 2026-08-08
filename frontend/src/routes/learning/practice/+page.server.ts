import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import {
  backendRequest,
  requireBackendJson,
  readTypedJsonOrNull
} from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearningPracticeSession, LearningPracticeStack } from "$lib/types/practice";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  const bootstrap = await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");
  const breadcrumbs = [{ label: "Lernraum", href: "/learning" }, { label: "Üben" }];
  if (!bootstrap.practice_enabled) {
    return {
      breadcrumbs,
      hidePageHeading: true,
      pageTitle: "Üben",
      enabled: false,
      stacks: [] as LearningPracticeStack[],
      activeSession: null as LearningPracticeSession | null
    };
  }

  const [stackResponse, activeSession] = await Promise.all([
    requireBackendJson<{ stacks: LearningPracticeStack[] }>(
      fetch,
      cookies,
      "/api/learning/practice/stacks",
      { authRedirectPath }
    ),
    readTypedJsonOrNull<LearningPracticeSession>(
      fetch,
      cookies,
      "/api/learning/practice/sessions/active"
    )
  ]);
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
    activeSession
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
