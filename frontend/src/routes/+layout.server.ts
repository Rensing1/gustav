import type { LayoutServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { SessionBootstrap } from "$lib/types/session-bootstrap";

export const load: LayoutServerLoad = async ({ fetch, cookies }) => {
  const bootstrap = await readTypedJsonOrNull<SessionBootstrap>(
    fetch,
    cookies,
    "/api/app/session-bootstrap"
  );
  const themeCookie = cookies.get("gustav_theme");
  const theme = themeCookie === "dark" ? "dark" : "light";

  return {
    bootstrap,
    theme
  };
};
