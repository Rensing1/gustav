import { backendRequest } from "$lib/server/api";
import type { Cookies } from "@sveltejs/kit";

type ProxyBackendWriteArgs = {
  fetchFn: typeof fetch;
  cookies: Cookies;
  path: string;
  method: "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

type ProxyBackendReadArgs = {
  fetchFn: typeof fetch;
  cookies: Cookies;
  path: string;
};

function copyProxyHeaders(response: Response): Headers {
  const contentType = response.headers.get("content-type");
  const headers = new Headers();
  if (contentType) {
    headers.set("content-type", contentType);
  }
  for (const headerName of ["cache-control", "vary"]) {
    const headerValue = response.headers.get(headerName);
    if (headerValue) {
      headers.set(headerName, headerValue);
    }
  }
  return headers;
}

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

  const text = response.status === 204 ? "" : await response.text();
  return new Response(text, {
    status: response.status,
    headers: copyProxyHeaders(response)
  });
}

/**
 * Proxy a browser-facing read request through the SvelteKit BFF.
 *
 * Why:
 * - Live browser routes must preserve backend response headers because the
 *   backend contract marks the payloads as personalized and non-cacheable.
 * - Read routes must enforce the same internal same-origin boundary as write
 *   routes so browser-facing BFF traffic stays consistent.
 * - Keeping this helper central avoids three route-local reimplementations for
 *   summary, detail-sheet and delta.
 */
export async function proxyBackendRead({
  fetchFn,
  cookies,
  path
}: ProxyBackendReadArgs): Promise<Response> {
  const response = await backendRequest(fetchFn, cookies, path, {
    method: "GET",
    includeSameOrigin: true
  });
  const body = response.status === 204 ? null : await response.text();
  return new Response(body, {
    status: response.status,
    headers: copyProxyHeaders(response)
  });
}
