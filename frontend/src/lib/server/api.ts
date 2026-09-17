import { env } from "$env/dynamic/private";
import { getRequestEvent } from "$app/server";
import { error, redirect } from "@sveltejs/kit";
import type { Cookies } from "@sveltejs/kit";

export function buildApiUrl(path: string): string {
  return new URL(path, env.API_INTERNAL_BASE_URL || "http://gustav-alpha2:8000").toString();
}

export class BackendRequestError extends Error {
  response: Response;

  constructor(response: Response, message?: string) {
    super(message || `Backend request failed with ${response.status}`);
    this.response = response;
  }
}

type BackendRequestOptions = {
  method?: string;
  body?: BodyInit | null;
  headers?: HeadersInit;
  includeSameOrigin?: boolean;
  authRedirectPath?: string;
};

export async function backendRequest(
  fetchFn: typeof fetch, cookies: Cookies, path: string, options?: BackendRequestOptions
): Promise<Response> {
  const headers = new Headers(options?.headers);
  const session = cookies.get("gustav_session");
  if (session) headers.set("cookie", `gustav_session=${encodeURIComponent(session)}`);
  // Forward provenance verbatim. Only FastAPI decides whether this origin is trusted.
  const request = getRequestEvent().request;
  for (const name of ["origin", "referer"]) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const method = (options?.method || "GET").toUpperCase();
  let response: Response;
  try {
    response = await fetchFn(buildApiUrl(path), { method, body: options?.body, headers });
  } catch {
    // Preserve drafts and authentication when the backend cannot be reached.
    return new Response(JSON.stringify({ error: "service_unavailable" }), {
      status: 503, headers: { "content-type": "application/json", "cache-control": "private, no-store" }
    });
  }
  if (response.status === 401 && options?.authRedirectPath && (method === "GET" || method === "HEAD")) {
    throw redirect(302, `/auth/continue?redirect=${encodeURIComponent(options.authRedirectPath)}`);
  }
  // A write is never retried or redirected here: its caller retains the draft.
  return response;
}

export async function requireBackendJson<T>(
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string,
  options?: BackendRequestOptions
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
    throw error(response.status, response.status === 503 ? "Die Anmeldung kann gerade nicht geprüft werden. Bitte versuche es gleich erneut." : "Die Anfrage konnte nicht abgeschlossen werden.");
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
