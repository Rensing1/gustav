import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";
import { clearCourseInviteIntent, readCourseInviteIntent } from "$lib/server/course-invite-intent";
import { redirect } from "@sveltejs/kit";

export const GET: RequestHandler = async ({ fetch, cookies }) => {
  const intent = readCourseInviteIntent(cookies);
  if (!intent?.accepted) {
    clearCourseInviteIntent(cookies);
    throw redirect(303, "/invite/result?reason=invalid");
  }
  const response = await backendRequest(fetch, cookies, "/api/course-invitations/redeem", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: intent.token }),
    includeSameOrigin: true,
    authRedirectPath: "/invite/complete"
  });
  if (response.status === 201 || response.status === 200) {
    const result = await response.json() as { course_id: string };
    clearCourseInviteIntent(cookies);
    throw redirect(303, `/learning/courses/${encodeURIComponent(result.course_id)}`);
  }
  if ([403, 404, 409].includes(response.status)) {
    clearCourseInviteIntent(cookies);
    const reason = response.status === 409 ? "removed" : "invalid";
    throw redirect(303, `/invite/result?reason=${reason}`);
  }
  throw redirect(303, "/invite/result?reason=temporary");
};
