import { render, screen } from "@testing-library/svelte";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

import WorkspaceSettingsMenu from "./WorkspaceSettingsMenu.svelte";

describe("WorkspaceSettingsMenu", () => {
  function renderMenu() {
    return render(WorkspaceSettingsMenu, {
      props: {
        open: true,
        tocOpen: true,
        splitView: false,
        showSplitToggle: true,
        tocWidth: 17,
        workspaceWidth: 64,
        splitRatio: 50,
        tocGap: 1.3,
        paneGap: 1.3,
        fontScale: 1,
        onToggleMenu: vi.fn(),
        onToggleToc: vi.fn(),
        onToggleSplitView: vi.fn(),
        onResetLayout: vi.fn(),
        onUpdateTocWidth: vi.fn(),
        onPreviewWorkspaceWidth: vi.fn(),
        onCommitWorkspaceWidth: vi.fn(),
        onPreviewFontScale: vi.fn(),
        onCommitFontScale: vi.fn(),
        onUpdateSplitRatio: vi.fn(),
        onUpdateTocGap: vi.fn(),
        onUpdatePaneGap: vi.fn()
      }
    });
  }

  it("renders styled controls for toggles, ranges and number inputs", () => {
    const { container } = renderMenu();

    expect(screen.getByRole("dialog", { name: "Layout-Einstellungen" })).toBeInTheDocument();
    expect(container.querySelectorAll(".workspace-settings-menu__checkbox")).toHaveLength(2);
    expect(container.querySelectorAll(".workspace-settings-menu__range")).toHaveLength(6);
    expect(container.querySelectorAll(".workspace-settings-menu__number")).toHaveLength(6);
    expect(container.querySelector(".workspace-settings-menu__number:disabled")).not.toBeNull();
  });

  it("defines a fully themed control contract instead of relying on native browser chrome", () => {
    const cssPath = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "../../styles/design-system.css"
    );
    const css = readFileSync(cssPath, "utf8");

    expect(css).toMatch(/\.workspace-settings-menu__checkbox\s*\{[^}]*appearance:\s*none;[^}]*background:\s*var\(--color-bg-surface\);/s);
    expect(css).toMatch(/\.workspace-settings-menu__checkbox:checked::after\s*\{[^}]*border-color:\s*#ffffff;/s);
    expect(css).toMatch(/\.workspace-settings-menu__range\s*\{[^}]*appearance:\s*none;[^}]*background:\s*transparent;/s);
    expect(css).toMatch(/\.workspace-settings-menu__range::-webkit-slider-thumb\s*\{[^}]*border:\s*2px solid var\(--color-accent\);[^}]*background:\s*var\(--color-bg-surface\);/s);
    expect(css).toMatch(/\.workspace-settings-menu__number\s*\{[^}]*background:\s*var\(--color-bg-surface\);[^}]*color:\s*var\(--color-text\);/s);
    expect(css).toMatch(/\[data-theme="dark"\] \.workspace-settings-menu__number\s*\{[^}]*background:\s*var\(--color-bg-elevated\);/s);
  });
});
