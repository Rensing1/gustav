import type { LayoutServerLoad } from "./$types";

import { readAppSessionActive, readTypedJsonOrNull } from "$lib/server/api";
import { parseThemePreference, THEME_COOKIE_NAME } from "$lib/server/theme";
import type { SessionBootstrap } from "$lib/types/session-bootstrap";

export const load: LayoutServerLoad = async ({ fetch, cookies }) => {
  const bootstrap = await readTypedJsonOrNull<SessionBootstrap>(
    fetch,
    cookies,
    "/api/app/session-bootstrap"
  );
  const theme = parseThemePreference(cookies.get(THEME_COOKIE_NAME));
  const appSessionActive = bootstrap ? true : await readAppSessionActive(fetch, cookies);

  return {
    bootstrap,
    appSessionActive,
    theme
  };
};
