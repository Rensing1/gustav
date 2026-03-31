import { backendRequest } from "$lib/server/api";
import type { Cookies } from "@sveltejs/kit";

type ProxyBackendWriteArgs = {
  fetchFn: typeof fetch;
  cookies: Cookies;
  path: string;
  method: "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

/**
 * Proxy a browser-facing write request through the SvelteKit BFF.
 *
 * Why:
 * - Browser graph interactions must not talk to backend write endpoints
 *   directly because authentication and same-origin enforcement are handled
 *   via the BFF session.
 * - The proxy keeps the response body/status stable while reusing the existing
 *   backend API contract.
 */
export async function proxyBackendWrite({
  fetchFn,
  cookies,
  path,
  method,
  body
}: ProxyBackendWriteArgs): Promise<Response> {
  const response = await backendRequest(fetchFn, cookies, path, {
    method,
    body: body === undefined ? null : JSON.stringify(body),
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    includeSameOrigin: true
  });

  const contentType = response.headers.get("content-type") ?? "application/json";
  const text = response.status === 204 ? "" : await response.text();

  return new Response(text, {
    status: response.status,
    headers: { "content-type": contentType }
  });
}
