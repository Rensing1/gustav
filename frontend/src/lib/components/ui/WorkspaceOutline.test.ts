import { render, screen } from "@testing-library/svelte";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

import WorkspaceOutline from "./WorkspaceOutline.svelte";

describe("WorkspaceOutline", () => {
  it("renders grouped outline items and marks active entries", () => {
    render(WorkspaceOutline, {
      props: {
        title: "Inhaltsverzeichnis",
        groups: [
          {
            id: "group-1",
            title: "Modul Graphen",
            items: [
              { key: "material:1", title: "Einführung" },
              { key: "task:1", title: "Begriffe präzisieren" }
            ]
          }
        ],
        activeItemKeys: ["task:1"],
        onOpenItem: vi.fn()
      }
    });

    expect(screen.getByRole("heading", { name: "Inhaltsverzeichnis" })).toBeInTheDocument();
    expect(screen.getByText("Modul Graphen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Begriffe präzisieren" })).toHaveClass("workspace-outline__item--active");
  });

  it("keeps long item labels inside a dedicated text wrapper for reliable wrapping", () => {
    render(WorkspaceOutline, {
      props: {
        title: "Inhaltsverzeichnis",
        groups: [
          {
            id: "group-1",
            title: "Erkundung",
            items: [
              {
                key: "task:long",
                title: "Was tut die Europäische Union für mich und wie verändert sie meinen Alltag?"
              }
            ]
          }
        ],
        activeItemKeys: [],
        onOpenItem: vi.fn()
      }
    });

    const label = screen.getByText("Was tut die Europäische Union für mich und wie verändert sie meinen Alltag?");
    expect(label).toHaveClass("workspace-outline__item-label");
    expect(label.closest(".workspace-outline__item-copy")).not.toBeNull();
  });

  it("uses a denser, more technical stitch-like typography contract", () => {
    const cssPath = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "../../styles/design-system.css"
    );
    const designDocPath = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "../../../../../docs/DESIGN.md"
    );
    const css = readFileSync(cssPath, "utf8");
    const designDoc = readFileSync(designDocPath, "utf8");

    expect(designDoc).toContain("### 7.3 Flächen");
    expect(designDoc).toContain("## 13. Verbotene Alt-Muster");
    expect(css).toMatch(/\.workspace-outline\s*\{[^}]*gap:\s*0\.65rem;[^}]*padding:\s*0\.82rem 0\.85rem 0\.9rem;/s);
    expect(css).toMatch(/\.workspace-outline__header h2\s*\{[^}]*font-family:\s*var\(--font-mono\);[^}]*font-size:\s*0\.98rem;[^}]*text-transform:\s*uppercase;/s);
    expect(css).toMatch(/\.workspace-outline__group-title\s*\{[^}]*font-family:\s*var\(--font-mono\);[^}]*font-size:\s*0\.76rem;[^}]*letter-spacing:\s*0\.18em;/s);
    expect(css).toMatch(/\.workspace-outline__item-label\s*\{[^}]*font-family:\s*var\(--font-mono\);[^}]*font-size:\s*0\.96rem;[^}]*line-height:\s*1\.4;/s);
    expect(css).toMatch(/\.workspace-outline__body\s*\{[^}]*gap:\s*0\.82rem;/s);
    expect(css).toMatch(/\.workspace-outline__group\s*\{[^}]*gap:\s*0\.62rem;/s);
    expect(css).toMatch(/\.workspace-outline__items\s*\{[^}]*gap:\s*0\.08rem;/s);
    expect(css).toMatch(/\.workspace-outline__item\s*\{[^}]*min-height:\s*1\.82rem;[^}]*padding:\s*0\.24rem 0 0\.24rem 0\.95rem;/s);
    expect(css).toMatch(/\.workspace-outline__item--active\s*\{[^}]*background:\s*transparent;/s);
    expect(css).not.toMatch(/\.workspace-outline__item--active::after\s*\{/s);
    expect(css).not.toMatch(/\.workspace-outline__item--active \.workspace-outline__item-label\s*\{[^}]*color:\s*var\(--color-accent\);/s);
    expect(css).not.toMatch(/\.workspace-outline__item--active \.workspace-outline__item-label\s*\{[^}]*font-weight:\s*700;/s);
  });
});
