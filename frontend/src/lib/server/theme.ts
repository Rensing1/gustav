import type { Cookies } from "@sveltejs/kit";

import type { ThemePreference } from "$lib/types/theme";

export const THEME_COOKIE_NAME = "gustav_theme";

export function parseThemePreference(value: string | undefined): ThemePreference {
  return value === "dark" ? "dark" : "light";
}

export function persistThemePreference(
  cookies: Cookies,
  url: URL,
  theme: ThemePreference
): void {
  cookies.set(THEME_COOKIE_NAME, theme, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: url.protocol === "https:"
  });
}
