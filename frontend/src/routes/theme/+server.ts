import { json } from "@sveltejs/kit";

import { parseThemePreference, persistThemePreference } from "$lib/server/theme";
import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ cookies, request, url }) => {
  let body: { theme?: string };

  try {
    body = (await request.json()) as { theme?: string };
  } catch {
    return json({ error: "bad_request", detail: "invalid_json" }, { status: 400 });
  }

  const rawTheme = String(body.theme ?? "").trim();
  if (rawTheme !== "light" && rawTheme !== "dark") {
    return json({ error: "bad_request", detail: "invalid_theme" }, { status: 400 });
  }

  const theme = parseThemePreference(rawTheme);
  persistThemePreference(cookies, url, theme);

  return json({ theme });
};
