import { redirect } from "@sveltejs/kit";
import type { Cookies } from "@sveltejs/kit";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { SessionBootstrap } from "$lib/types/session-bootstrap";

export type AppSpace = "learning" | "teaching" | "diagnostics" | "live";

export function currentPath(url: URL): string {
  const path = `${url.pathname}${url.search}`;
  return path || "/";
}

function loginHref(path: string): string {
  const params = new URLSearchParams({ redirect: path || "/" });
  return `/auth/login?${params.toString()}`;
}

export async function requireSessionBootstrap(
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string
): Promise<SessionBootstrap> {
  const bootstrap = await readTypedJsonOrNull<SessionBootstrap>(
    fetchFn,
    cookies,
    "/api/app/session-bootstrap"
  );
  if (!bootstrap) {
    throw redirect(302, loginHref(path));
  }
  return bootstrap;
}

export async function requireSpaceBootstrap(
  fetchFn: typeof fetch,
  cookies: Cookies,
  path: string,
  space: AppSpace
): Promise<SessionBootstrap> {
  const bootstrap = await requireSessionBootstrap(fetchFn, cookies, path);
  if (!bootstrap.spaces.includes(space)) {
    throw redirect(303, bootstrap.start_target);
  }
  return bootstrap;
}
