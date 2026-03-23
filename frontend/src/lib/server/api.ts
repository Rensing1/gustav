import { env } from "$env/dynamic/private";
import { buildBackendSessionCookieHeader, readFrontendSessionCookie } from "$lib/server/session";
import type { Cookies } from "@sveltejs/kit";

const DEFAULT_API_INTERNAL_BASE_URL = "http://gustav-alpha2:8000";

export function buildApiUrl(path: string): string {
  const baseUrl = env.API_INTERNAL_BASE_URL || DEFAULT_API_INTERNAL_BASE_URL;
  return new URL(path, baseUrl).toString();
}

export async function readJsonOrNull(
  // Generic helper so loaders can retain concrete response contracts.
  // This keeps SvelteKit-generated route types aligned with backend read-models.
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string
): Promise<unknown | null> {
  const headers = new Headers();
  const backendCookie = buildBackendSessionCookieHeader(readFrontendSessionCookie(cookies));
  if (backendCookie) {
    headers.set("cookie", backendCookie);
  }

  const response = await fetchFn(buildApiUrl(path), {
    method: "GET",
    headers
  });

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
