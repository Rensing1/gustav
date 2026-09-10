import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";

describe("shared Keycloak appearance initialization", () => {
  it.each([
    ["dark", "light", false, "dark"],
    ["light", "dark", true, "light"],
    ["invalid", "dark", false, "dark"],
    [null, null, true, "dark"],
    [null, "legacy-theme", false, "light"]
  ])("uses validated hint, then saved choice, then system", (hint, saved, darkSystem, expected) => {
    const script = readFileSync(resolve(process.cwd(), "../keycloak/themes/gustav/login/resources/js/theme.js"), "utf8");
    const attributes = new Map();
    const storage = new Map(saved ? [["gustav-theme", saved]] : []);
    const url = new URL("https://id.localhost/login?client_id=gustav-web");
    if (hint) url.searchParams.set("gustav_theme", hint);
    let ready: (() => void) | undefined;
    let click: (() => void) | undefined;
    const button = { textContent: "", setAttribute: (name: string, value: string) => attributes.set(name, value), addEventListener: (_: string, fn: () => void) => { click = fn; } };
    let replacedUrl = "";
    runInNewContext(script, {
      URL,
      window: { location: { href: url.href }, matchMedia: () => ({ matches: darkSystem }) },
      history: { state: { preserved: true }, replaceState: (_: unknown, __: string, value: string) => { replacedUrl = value; } },
      localStorage: { getItem: (key: string) => storage.get(key), setItem: (key: string, value: string) => storage.set(key, value) },
      document: {
        documentElement: { setAttribute: (key: string, value: string) => attributes.set(key, value) },
        getElementById: () => button,
        addEventListener: (_: string, fn: () => void) => { ready = fn; }
      }
    });
    expect(attributes.get("data-theme")).toBe(expected);
    ready?.();
    expect(button.textContent).toMatch(/Helle Darstellung|Dunkle Darstellung/);
    click?.();
    expect(storage.get("gustav-theme")).toBe(expected === "dark" ? "light" : "dark");
    if (hint) {
      expect(new URL(replacedUrl).searchParams.has("gustav_theme")).toBe(false);
      expect(new URL(replacedUrl).searchParams.get("client_id")).toBe("gustav-web");
    }
  });
});
