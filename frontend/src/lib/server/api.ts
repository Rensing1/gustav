import { env } from "$env/dynamic/private";
import {
  buildBackendAuthorizationHeader,
  readFreshTokenSession
} from "$lib/server/session";
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
  const createHeaders = async (forceRefresh = false): Promise<Headers> => {
    const headers = new Headers();
    const tokenSession = await readFreshTokenSession(cookies, fetchFn, { forceRefresh });
    const backendAuthorization = buildBackendAuthorizationHeader(tokenSession?.accessToken);
    if (backendAuthorization) {
      headers.set("authorization", backendAuthorization);
    }
    return headers;
  };

  let response = await fetchFn(buildApiUrl(path), {
    method: "GET",
    headers: await createHeaders()
  });

  if (response.status === 401) {
    response = await fetchFn(buildApiUrl(path), {
      method: "GET",
      headers: await createHeaders(true)
    });
  }

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
