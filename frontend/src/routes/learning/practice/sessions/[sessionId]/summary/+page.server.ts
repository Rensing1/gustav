import { error, redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearningPracticeSession } from "$lib/types/practice";

export const load: PageServerLoad = async ({ fetch, cookies, parent, params, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");
  const session = await requireBackendJson<LearningPracticeSession>(
    fetch,
    cookies,
    `/api/learning/practice/sessions/${encodeURIComponent(params.sessionId)}`,
    { authRedirectPath }
  );

  if (session.status !== "ended") {
    throw redirect(303, "/learning/practice");
  }
  if (!session.end_reason || !session.summary) {
    throw error(500, "practice_summary_unavailable");
  }

  return {
    breadcrumbs: [
      { label: "Lernraum", href: "/learning" },
      { label: "Üben", href: "/learning/practice" },
      { label: "Abschluss" }
    ],
    hidePageHeading: true,
    pageTitle: "Übung abgeschlossen",
    session,
    nowIso: new Date().toISOString()
  };
};
