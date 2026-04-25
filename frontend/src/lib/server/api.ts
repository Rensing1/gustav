import { env } from "$env/dynamic/private";
import {
  buildBackendAuthorizationHeader,
  readFreshTokenSession
} from "$lib/server/session";
import type { Cookies } from "@sveltejs/kit";

const DEFAULT_API_INTERNAL_BASE_URL = "http://gustav-alpha2:8000";
const APP_SESSION_COOKIE_NAME = "gustav_session";

export function buildApiUrl(path: string): string {
  const baseUrl = env.API_INTERNAL_BASE_URL || DEFAULT_API_INTERNAL_BASE_URL;
  return new URL(path, baseUrl).toString();
}

export async function readAppSessionActive(fetchFn: typeof fetch, cookies: Cookies): Promise<boolean> {
  const sessionId = cookies.get(APP_SESSION_COOKIE_NAME);
  if (!sessionId) {
    return false;
  }
  try {
    const response = await fetchFn(buildApiUrl("/api/me"), {
      method: "GET",
      headers: {
        cookie: `${APP_SESSION_COOKIE_NAME}=${encodeURIComponent(sessionId)}`
      }
    });
    return response.ok;
  } catch {
    return false;
  }
}

function internalOrigin(): string {
  const apiBaseUrl = env.API_INTERNAL_BASE_URL || DEFAULT_API_INTERNAL_BASE_URL;
  try {
    return new URL(apiBaseUrl).origin;
  } catch {
    return DEFAULT_API_INTERNAL_BASE_URL;
  }
}

async function createAuthHeaders(
  fetchFn: typeof fetch,
  cookies: Cookies,
  options?: {
    forceRefresh?: boolean;
    includeSameOrigin?: boolean;
    headers?: HeadersInit;
  }
): Promise<Headers> {
  const headers = new Headers(options?.headers);
  const tokenSession = await readFreshTokenSession(cookies, fetchFn, {
    forceRefresh: options?.forceRefresh
  });
  const backendAuthorization = buildBackendAuthorizationHeader(tokenSession?.accessToken);
  if (backendAuthorization) {
    headers.set("authorization", backendAuthorization);
  }
  if (options?.includeSameOrigin) {
    headers.set("origin", internalOrigin());
    headers.set("referer", internalOrigin());
  }
  return headers;
}

export class BackendRequestError extends Error {
  response: Response;

  constructor(response: Response, message?: string) {
    super(message || `Backend request failed with ${response.status}`);
    this.response = response;
  }
}

export async function backendRequest(
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string,
  options?: {
    method?: string;
    body?: BodyInit | null;
    headers?: HeadersInit;
    includeSameOrigin?: boolean;
  }
): Promise<Response> {
  const requestInit = {
    method: options?.method || "GET",
    body: options?.body,
    headers: await createAuthHeaders(fetchFn, cookies, {
      headers: options?.headers,
      includeSameOrigin: options?.includeSameOrigin
    })
  };

  let response = await fetchFn(buildApiUrl(path), requestInit);
  if (response.status !== 401) {
    return response;
  }

  return await fetchFn(buildApiUrl(path), {
    ...requestInit,
    headers: await createAuthHeaders(fetchFn, cookies, {
      forceRefresh: true,
      headers: options?.headers,
      includeSameOrigin: options?.includeSameOrigin
    })
  });
}

export async function requireBackendJson<T>(
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string,
  options?: {
    method?: string;
    body?: BodyInit | null;
    headers?: HeadersInit;
    includeSameOrigin?: boolean;
  }
): Promise<T> {
  const response = await backendRequest(fetchFn, cookies, path, options);
  if (!response.ok) {
    throw new BackendRequestError(response);
  }
  return (await response.json()) as T;
}

export async function readJsonOrNull(
  // Generic helper so loaders can retain concrete response contracts.
  // This keeps SvelteKit-generated route types aligned with backend read-models.
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string
): Promise<unknown | null> {
  const response = await backendRequest(fetchFn, cookies, path, { method: "GET" });

  if (response.status === 401 || response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Backend bootstrap request failed with ${response.status}`);
  }
  return await response.json();
}

export async function readTypedJsonOrNull<T>(
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string
) : Promise<T | null> {
  return (await readJsonOrNull(fetchFn, cookies, path)) as T | null;
}
