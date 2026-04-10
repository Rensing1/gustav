import { describe, expect, it, vi } from "vitest";

import { parseThemePreference, persistThemePreference } from "./theme";

describe("theme preference", () => {
  it("stores a dark theme cookie for later server renders", () => {
    const setCookie = vi.fn();

    persistThemePreference(
      {
        set: setCookie
      } as never,
      new URL("http://localhost/theme"),
      "dark"
    );

    expect(setCookie).toHaveBeenCalledWith(
      "gustav_theme",
      "dark",
      expect.objectContaining({
        path: "/",
        httpOnly: true,
        sameSite: "lax",
        secure: false
      })
    );
  });

  it("parses only known theme values", () => {
    expect(parseThemePreference("dark")).toBe("dark");
    expect(parseThemePreference("light")).toBe("light");
    expect(parseThemePreference("sepia")).toBe("light");
    expect(parseThemePreference(undefined)).toBe("light");
  });
});
