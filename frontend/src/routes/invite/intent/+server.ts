import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";
import { setCourseInviteIntent } from "$lib/server/course-invite-intent";
import { json } from "@sveltejs/kit";

const headers = { "Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer" };

export const POST: RequestHandler = async ({ request, fetch, cookies }) => {
  const body = await request.json().catch(() => null) as { token?: unknown } | null;
  if (typeof body?.token !== "string") {
    return json({ error: "not_found" }, { status: 404, headers });
  }
  const response = await backendRequest(fetch, cookies, "/api/course-invitations/preview", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token: body.token })
  });
  if (!response.ok) {
    return json({ error: "not_found" }, { status: 404, headers });
  }
  const preview = await response.json() as { course_title: string; expires_at: string };
  const expiresAt = Math.floor(new Date(preview.expires_at).getTime() / 1000);
  if (!Number.isFinite(expiresAt) || expiresAt <= Math.floor(Date.now() / 1000)) {
    return json({ error: "not_found" }, { status: 404, headers });
  }
  setCourseInviteIntent(cookies, { token: body.token, accepted: false, expiresAt });
  return json(preview, { status: 200, headers });
};
