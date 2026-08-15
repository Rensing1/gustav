import type { RequestHandler } from "./$types";

import { readCourseInviteIntent, setCourseInviteIntent } from "$lib/server/course-invite-intent";
import { json } from "@sveltejs/kit";

export const POST: RequestHandler = async ({ request, cookies }) => {
  const intent = readCourseInviteIntent(cookies);
  if (!intent) return json({ error: "not_found" }, { status: 404 });
  const body = await request.json().catch(() => null) as { mode?: unknown } | null;
  const mode = String(body?.mode || "");
  if (mode !== "register" && mode !== "login") {
    return json({ error: "bad_request" }, { status: 400 });
  }
  setCourseInviteIntent(cookies, { ...intent, accepted: true });
  return json(
    {
      redirect: mode === "register"
        ? "/register?redirect=/invite/complete"
        : "/auth/login?redirect=/invite/complete"
    },
    { headers: { "Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer" } }
  );
};
