import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { readWorkspaceCssBundle } from "./test-css-bundle";

describe("learner workspace theme contract", () => {
  it("keeps the learner top bar on neutral theme surfaces", () => {
    const css = readWorkspaceCssBundle(import.meta.dirname);
    const topbarRule = css.match(/\.app-topbar--learner-unit\s*\{(?<body>[^}]*)\}/s)?.groups?.body ?? "";

    expect(topbarRule).toContain("var(--color-bg-surface)");
    expect(topbarRule).toContain("var(--color-bg-base)");
    expect(topbarRule).not.toMatch(/rgba?\(|#[0-9a-f]{3,8}|\bwhite\b/i);
  });

  it("keeps browser chrome colors aligned with the central theme backgrounds", () => {
    const layout = readFileSync(path.resolve(import.meta.dirname, "../../routes/+layout.svelte"), "utf8");
    const appShell = readFileSync(path.resolve(import.meta.dirname, "../../app.html"), "utf8");

    expect(layout).toContain('currentTheme === "dark" ? "#121212" : "#f9f9f9"');
    expect(appShell).toContain('<meta name="theme-color" content="#f9f9f9" />');
    expect(layout).not.toMatch(/#272E33|#FAF4ED/i);
    expect(appShell).not.toMatch(/#faf4ed/i);
  });
});
