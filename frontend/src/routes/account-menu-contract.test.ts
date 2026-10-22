import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { readGlobalCssBundle } from "$lib/styles/test-css-bundle";

describe("account menu contract", () => {
  it("renders the topbar tools as one group with a minimal account menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");
    const headerSource = readFileSync(path.resolve(currentDir, "../lib/components/ui/AppHeader.svelte"), "utf8");

    expect(layoutSource).toContain("<AppHeader");
    expect(headerSource).toContain('<div class="global-header__tools">');
    expect(headerSource).toContain('<ThemeToggle {currentTheme} {onToggle} />');
    expect(headerSource).toContain('<details class="global-header__account"');
    expect(headerSource).not.toContain("Angemeldet als");
  });

  it("keeps the account actions as dedicated menu rows", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const headerSource = readFileSync(path.resolve(currentDir, "../lib/components/ui/AppHeader.svelte"), "utf8");

    expect(headerSource).toContain('<a href="/profile">Profil</a>');
    expect(headerSource).toContain('<a href="/auth/logout">Abmelden</a>');
    expect(headerSource).toContain('class="global-header__panel"');
  });

  it("keeps the role-aware concern box visible outside the account menu", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const layoutSource = readFileSync(path.resolve(currentDir, "+layout.svelte"), "utf8");
    const headerSource = readFileSync(path.resolve(currentDir, "../lib/components/ui/AppHeader.svelte"), "utf8");

    expect(layoutSource).toContain("function concernBoxHref(): string");
    expect(layoutSource).toContain("concernHref={data.bootstrap ? concernBoxHref() : undefined}");
    expect(headerSource).toContain('class="global-header__concern" href={concernHref}');
    expect(headerSource).toContain('{#if contextItems && concernHref}<a href={concernHref}>Kummerkasten</a>{/if}');
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

  it("defines the calm global background without overriding it in the shell", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../lib/styles/app.css"), "utf8");
    const globalCss = readGlobalCssBundle(path.resolve(currentDir, "../lib/styles"));

    expect(appCss).toMatch(/html,\s*body\s*\{[^}]*background-color:\s*var\(--color-bg-base\);/s);
    expect(appCss).not.toMatch(/html,\s*body\s*\{[^}]*radial-gradient/s);
    expect(appCss).toMatch(/\.app-shell\s*\{[^}]*background:\s*transparent;/s);
    expect(globalCss).not.toMatch(/body\s*\{[^}]*background:\s*var\(--color-bg-base\);/s);
  });
});
