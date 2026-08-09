import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { readGlobalCssBundle } from "$lib/styles/test-css-bundle";

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

  it("keeps the role-aware concern box visible outside the account menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");
    const accountPanelStart = layoutSource.indexOf('<div class="account-menu__panel">');
    const accountPanelSource = layoutSource.slice(accountPanelStart);

    expect(layoutSource).toContain("function concernBoxHref(): string");
    expect(layoutSource).toContain('class="app-topbar-concern-link"');
    expect(layoutSource).toContain('href={concernBoxHref()}');
    expect(layoutSource).toContain('aria-current={isActive(concernBoxHref()) ? "page" : undefined}');
    expect(layoutSource).toMatch(/app-topbar-concern-link[\s\S]*?<div class="app-topbar-tools">/);
    expect(accountPanelSource).not.toContain('href="/learning/kummerkasten"');
    expect(accountPanelSource).not.toContain('href="/teaching/kummerkasten"');
  });

  it("keeps all topbar actions reachable on narrow screens", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");

    expect(cssSource).toMatch(/\.app-topbar-concern-link\s*\{[^}]*height:\s*var\(--topbar-tool-height\);/s);
    expect(cssSource).toMatch(/@media \(max-width: 640px\)[\s\S]*?\.app-topbar-controls\s*\{[^}]*width:\s*100%;[^}]*justify-content:\s*space-between;/s);
    expect(cssSource).toMatch(/@media \(max-width: 640px\)[\s\S]*?\.account-trigger__name\s*\{[^}]*display:\s*none;/s);
  });

  it("styles the account trigger and panel with hard edges", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");
    const overrideSource = readFileSync(path.resolve(currentDir, "../lib/styles/overrides.css"), "utf8");

    expect(overrideSource).toMatch(/\.app-topbar-tools :is\(\.theme-toggle, \.account-trigger\)\s*\{[^}]*border-radius:\s*0;/s);
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
    const cssSource = readFileSync(path.resolve(currentDir, "../lib/styles/overrides.css"), "utf8");

    expect(cssSource).toMatch(/\.app-topbar-tools :is\(\.theme-toggle, \.account-trigger\)\s*\{[^}]*box-shadow:\s*2px 2px 0 0 color-mix\(in srgb, var\(--color-border\) 72%, transparent 28%\);/s);
    expect(cssSource).toMatch(/\.app-topbar-tools :is\(\.theme-toggle, \.account-trigger\):hover,[\s\S]*?box-shadow:\s*1px 1px 0 0 color-mix\(in srgb, var\(--color-border\) 92%, transparent 8%\);/s);
    expect(cssSource).not.toMatch(/\.app-topbar-tools :is\(\.theme-toggle, \.account-trigger\)\s*\{[^}]*box-shadow:\s*var\(--color-shadow\);/s);
  });

  it("defines a subtle dotted global background without overriding it in the shared themes", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");
    const tokenCss = readFileSync(path.resolve(currentDir, "../lib/styles/theme-tokens.css"), "utf8");
    const globalCss = readGlobalCssBundle(path.resolve(currentDir, "../lib/styles"));
    const authThemeCss = readFileSync(path.resolve(currentDir, "../lib/styles/auth-theme.css"), "utf8");

    expect(tokenCss).toMatch(/--app-bg-dot-color:\s*rgba\([^)]+\);/);
    expect(tokenCss).toContain("--app-bg-dot-size: 1.35px;");
    expect(tokenCss).toContain("--app-bg-dot-fade-size: 1.5px;");
    expect(tokenCss).toContain("--app-bg-dot-spacing: 1.75rem;");
    expect(appCss).toMatch(/html,\s*body\s*\{[^}]*background-color:\s*var\(--color-bg-base\);[^}]*radial-gradient\([\s\S]*?var\(--app-bg-dot-color\) var\(--app-bg-dot-size\),[\s\S]*?transparent var\(--app-bg-dot-fade-size\)[\s\S]*?background-size:\s*var\(--app-bg-dot-spacing\) var\(--app-bg-dot-spacing\);/s);
    expect(appCss).toMatch(/\.app-shell\s*\{[^}]*background:\s*transparent;/s);
    expect(globalCss).not.toMatch(/body\s*\{[^}]*background:\s*var\(--color-bg-base\);/s);
    expect(authThemeCss).toMatch(/\.design-auth-shell,[\s\S]*?\.kc-gustav\s*\{[^}]*radial-gradient\(circle,\s*var\(--app-bg-dot-color\)\s+1\.35px,\s*transparent\s+1\.5px\)/s);
  });
});
