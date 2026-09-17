import type { LayoutServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import { parseThemePreference, THEME_COOKIE_NAME } from "$lib/server/theme";
import type { SessionBootstrap } from "$lib/types/session-bootstrap";

export const load: LayoutServerLoad = async ({ fetch, cookies, url }) => {
  // Logout must remain reachable even when token refresh is unavailable.
  const publicAuthPage = ["/auth/problem", "/auth/logout", "/auth/logout/success"].includes(url.pathname);
  const bootstrap = publicAuthPage ? null : await readTypedJsonOrNull<SessionBootstrap>(
    fetch,
    cookies,
    "/api/app/session-bootstrap"
  );
  const theme = parseThemePreference(cookies.get(THEME_COOKIE_NAME));
  const appSessionActive = Boolean(bootstrap);

  return {
    bootstrap,
    appSessionActive,
    theme,
    workspaceLayout: "standard"
  };
};
