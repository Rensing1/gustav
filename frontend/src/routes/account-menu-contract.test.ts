import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("account menu contract", () => {
  it("renders the topbar tools as one group with a minimal account menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain('<div class="app-topbar-tools">');
    expect(layoutSource).toContain('<ThemeToggle currentTheme={currentTheme} onToggle={toggleTheme} />');
    expect(layoutSource).toContain('<details class="account-menu" bind:this={accountMenu}>');
    expect(layoutSource).not.toContain("Angemeldet als");
    expect(layoutSource).not.toContain('class="identity-meta"');
    expect(layoutSource).not.toContain('class="ghost-link" href="/profile"');
  });

  it("keeps the account actions as dedicated menu rows", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");

    expect(layoutSource).toContain('class="account-menu__action" href="/profile"');
    expect(layoutSource).toContain('class="account-menu__action" href="/auth/logout"');
    expect(layoutSource).toContain('class="account-menu__panel"');
  });

  it("styles the account trigger and panel with hard edges", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");

    expect(cssSource).toMatch(/\.account-trigger\s*\{[^}]*border-radius:\s*0;/s);
    expect(cssSource).toMatch(/\.account-menu__panel\s*\{[^}]*border-radius:\s*0;/s);
    expect(cssSource).toMatch(/\.account-menu__action\s*\{[^}]*border-top:\s*1px solid var\(--color-border\);/s);
    expect(cssSource).not.toMatch(/\.account-trigger\s*\{[^}]*border-radius:\s*999px;/s);
  });

  it("keeps a small gap and a shared height across the topbar tools", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");

    expect(cssSource).toMatch(/\.app-topbar-tools\s*\{[^}]*gap:\s*0\.35rem;/s);
    expect(cssSource).toMatch(/\.app-topbar-tools\s*\{[^}]*--topbar-tool-height:\s*2\.3rem;/s);
    expect(cssSource).toMatch(/\.app-topbar-tools \.theme-toggle\s*\{[^}]*width:\s*var\(--topbar-tool-height\);[^}]*height:\s*var\(--topbar-tool-height\);/s);
    expect(cssSource).toMatch(/\.account-trigger\s*\{[^}]*height:\s*var\(--topbar-tool-height\);/s);
    expect(cssSource).not.toMatch(/\.app-topbar-tools \.theme-toggle\s*\{[^}]*border-right:\s*none;/s);
  });

  it("renders the account initial as a centered tile", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");

    expect(cssSource).toMatch(/\.account-trigger__initial\s*\{[^}]*width:\s*var\(--topbar-tool-height\);[^}]*height:\s*var\(--topbar-tool-height\);/s);
    expect(cssSource).toMatch(/\.account-trigger__initial\s*\{[^}]*justify-self:\s*stretch;|\.account-trigger__initial\s*\{[^}]*align-self:\s*stretch;/s);
    expect(cssSource).toMatch(/\.account-trigger__initial\s*\{[^}]*place-items:\s*center;/s);
  });

  it("reduces the 3d effect for topbar tools without flattening them", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");

    expect(cssSource).toMatch(/\.app-topbar-tools \.theme-toggle\s*\{[^}]*box-shadow:\s*2px 2px 0 0 rgba\(27, 27, 27, 0\.72\);/s);
    expect(cssSource).toMatch(/\.account-trigger\s*\{[^}]*box-shadow:\s*2px 2px 0 0 rgba\(27, 27, 27, 0\.72\);/s);
    expect(cssSource).toMatch(/\.account-trigger:hover,[\s\S]*?box-shadow:\s*1px 1px 0 0 rgba\(27, 27, 27, 0\.92\);/s);
    expect(cssSource).not.toMatch(/\.app-topbar-tools \.theme-toggle\s*\{[^}]*box-shadow:\s*var\(--color-shadow\);/s);
    expect(cssSource).not.toMatch(/\.account-trigger\s*\{[^}]*box-shadow:\s*var\(--color-shadow\);/s);
  });

  it("defines a subtle dotted global background without overriding it in the shared themes", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");
    const designSystemCss = readFileSync(path.resolve(currentDir, "../lib/styles/design-system.css"), "utf8");
    const authThemeCss = readFileSync(path.resolve(currentDir, "../lib/styles/auth-theme.css"), "utf8");

    expect(appCss).toMatch(/--app-bg-dot-color:\s*rgba\([^)]+\);/);
    expect(appCss).toMatch(/html,\s*body\s*\{[^}]*background-color:\s*var\(--color-bg-base\);[^}]*radial-gradient\(circle,\s*var\(--app-bg-dot-color\)\s+1\.35px,\s*transparent\s+1\.5px\);[^}]*background-size:\s*1\.75rem 1\.75rem;/s);
    expect(appCss).toMatch(/\.app-shell\s*\{[^}]*background:\s*transparent;/s);
    expect(designSystemCss).not.toMatch(/body\s*\{[^}]*background:\s*var\(--color-bg-base\);/s);
    expect(authThemeCss).toMatch(/\.design-auth-shell,[\s\S]*?\.kc-gustav\s*\{[^}]*radial-gradient\(circle,\s*var\(--app-bg-dot-color\)\s+1\.35px,\s*transparent\s+1\.5px\)/s);
  });
});
