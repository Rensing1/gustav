import type { RequestEvent } from "@sveltejs/kit";

import { env } from "$env/dynamic/private";
import {
  buildBackendSessionCookieHeader,
  clearFrontendSessionCookie,
  extractBackendSessionId,
  readFrontendSessionCookie,
  setFrontendSessionCookie
} from "$lib/server/session";

const DEFAULT_API_INTERNAL_BASE_URL = "http://gustav-alpha2:8000";
const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-type",
  "location",
  "vary"
];

function buildBackendUrl(path: string, requestUrl: URL): string {
  const baseUrl = env.API_INTERNAL_BASE_URL || DEFAULT_API_INTERNAL_BASE_URL;
  const target = new URL(path, baseUrl);
  target.search = requestUrl.search;
  return target.toString();
}

export async function proxyBackendAuthGet(event: RequestEvent, path: string): Promise<Response> {
  const requestHeaders = new Headers();
  const backendCookie = buildBackendSessionCookieHeader(readFrontendSessionCookie(event.cookies));

  if (backendCookie) {
    requestHeaders.set("cookie", backendCookie);
  }

  const upstream = await event.fetch(buildBackendUrl(path, event.url), {
    method: "GET",
    headers: requestHeaders,
    redirect: "manual"
  });

  const responseHeaders = new Headers();
  for (const headerName of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(headerName);
    if (value) {
      responseHeaders.set(headerName, value);
    }
  }

  const backendSessionId = extractBackendSessionId(upstream.headers.get("set-cookie"));
  if (backendSessionId) {
    setFrontendSessionCookie(event.cookies, backendSessionId);
  } else if (path === "/auth/logout") {
    clearFrontendSessionCookie(event.cookies);
  }

  const body =
    upstream.status === 204 || (upstream.status >= 300 && upstream.status < 400)
      ? null
      : await upstream.text();

  return new Response(body, {
    status: upstream.status,
    headers: responseHeaders
  });
}
