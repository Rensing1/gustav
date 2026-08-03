import { render, screen } from "@testing-library/svelte";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

import { readGlobalCssBundle } from "$lib/styles/test-css-bundle";

import WorkspaceSettingsMenu from "./WorkspaceSettingsMenu.svelte";

describe("WorkspaceSettingsMenu", () => {
  function renderMenu() {
    return render(WorkspaceSettingsMenu, {
      props: {
        open: true,
        tocOpen: true,
        fontScale: 1,
        onToggleMenu: vi.fn(),
        onToggleToc: vi.fn(),
        onResetLayout: vi.fn(),
        onCommitFontScale: vi.fn()
      }
    });
  }

  it("offers only navigation, three font sizes and reset", () => {
    const { container } = renderMenu();

    expect(screen.getByRole("dialog", { name: "Layout-Einstellungen" })).toBeInTheDocument();
    expect(container.querySelectorAll(".workspace-settings-menu__checkbox")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Klein" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Standard" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Groß" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Darstellung zurücksetzen" })).toBeInTheDocument();
    expect(screen.queryByText("Zwei Ansichten")).not.toBeInTheDocument();
    expect(screen.queryByText("Breite Arbeitsrahmen")).not.toBeInTheDocument();
    expect(container.querySelector(".workspace-settings-menu__range")).toBeNull();
    expect(container.querySelector(".workspace-settings-menu__number")).toBeNull();
  });

  it("does not expose retired split or spacing controls in its component contract", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(path.resolve(currentDir, "WorkspaceSettingsMenu.svelte"), "utf8");

    expect(source).not.toContain("splitView");
    expect(source).not.toContain("workspaceWidth");
    expect(source).not.toContain("splitRatio");
    expect(source).not.toContain("paneGap");
    expect(source).not.toContain("tocGap");
  });

  it("defines themed checkbox and discrete font controls", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readGlobalCssBundle(path.resolve(currentDir, "../../styles"));

    expect(css).toMatch(/\.workspace-settings-menu__checkbox\s*\{[^}]*appearance:\s*none;[^}]*background:\s*var\(--color-bg-surface\);/s);
    expect(css).toMatch(/\.workspace-settings-menu__checkbox:checked::after\s*\{[^}]*border-color:\s*#ffffff;/s);
    expect(css).toMatch(/\.workspace-settings-menu__font-option\s*\{[^}]*border:/s);
    expect(css).toMatch(/\.workspace-settings-menu__font-option--active\s*\{[^}]*background:\s*var\(--color-text\);/s);
  });
});
