import type { RequestHandler } from "./$types";

import { backendRequest } from "$lib/server/api";

export const POST: RequestHandler = async ({ fetch, cookies, request, url }) => {
  const courseId = url.searchParams.get("course_id");
  const taskId = url.searchParams.get("task_id");

  if (!courseId || !taskId) {
    return new Response(JSON.stringify({ error: "invalid_request" }), {
      status: 400,
      headers: {
        "cache-control": "private, no-store",
        "content-type": "application/json"
      }
    });
  }

  const bodyText = await request.text();
  const idempotencyKey = request.headers.get("idempotency-key");
  const response = await backendRequest(
    fetch,
    cookies,
    `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`,
    {
      method: "POST",
      body: bodyText,
      includeSameOrigin: true,
      headers: {
        "content-type": request.headers.get("content-type") || "application/json",
        ...(idempotencyKey ? { "idempotency-key": idempotencyKey } : {})
      }
    }
  );
  const responseText = await response.text();

  return new Response(responseText, {
    status: response.status,
    headers: {
      "cache-control": "private, no-store",
      "content-type": response.headers.get("content-type") || "application/json"
    }
  });
};
