import { env } from "$env/dynamic/private";

const DEFAULT_API_INTERNAL_BASE_URL = "http://gustav-alpha2:8000";

export function buildApiUrl(path: string): string {
  const baseUrl = env.API_INTERNAL_BASE_URL || DEFAULT_API_INTERNAL_BASE_URL;
  return new URL(path, baseUrl).toString();
}

export async function readJsonOrNull(
  fetchFn: typeof fetch,
  request: Request,
  path: string
): Promise<unknown | null> {
  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  const cookie = request.headers.get("cookie");

  if (authorization) {
    headers.set("authorization", authorization);
  }
  if (cookie) {
    headers.set("cookie", cookie);
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

