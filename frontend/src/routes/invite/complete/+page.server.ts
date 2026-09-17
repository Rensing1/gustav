import type { Actions, PageServerLoad } from "./$types";

import { backendRequest } from "$lib/server/api";
import { clearCourseInviteIntent, readCourseInviteIntent } from "$lib/server/course-invite-intent";
import { fail, redirect } from "@sveltejs/kit";

/** Reading a return URL must never perform a membership-changing request. */
export const load: PageServerLoad = async ({ cookies, parent }) => {
  const intent = readCourseInviteIntent(cookies);
  if (!intent?.accepted) throw redirect(303, "/invite/result?reason=invalid");
  const { bootstrap } = await parent();
  if (!bootstrap) throw redirect(303, "/auth/continue?redirect=%2Finvite%2Fcomplete");
  return {};
};

export const actions: Actions = { default: async ({ fetch, cookies }) => {
  const intent = readCourseInviteIntent(cookies);
  if (!intent?.accepted) {
    clearCourseInviteIntent(cookies);
    throw redirect(303, "/invite/result?reason=invalid");
  }
  const response = await backendRequest(fetch, cookies, "/api/course-invitations/redeem", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: intent.token }),
    includeSameOrigin: true
  });
  if (response.status === 201 || response.status === 200) {
    const result = await response.json() as { course_id: string };
    clearCourseInviteIntent(cookies);
    throw redirect(303, `/learning/courses/${encodeURIComponent(result.course_id)}`);
  }
  if (response.status === 401) return fail(401, { message: "Bitte melde dich erneut an. Deine Einladung bleibt erhalten.", loginRequired: true });
  if (response.status >= 500) return fail(503, { message: "Der Beitritt ist gerade nicht möglich. Bitte versuche es gleich erneut.", loginRequired: false });
  if ([403, 404, 409].includes(response.status)) {
    clearCourseInviteIntent(cookies);
    const reason = response.status === 409 ? "removed" : "invalid";
    throw redirect(303, `/invite/result?reason=${reason}`);
  }
  throw redirect(303, "/invite/result?reason=temporary");
} };
