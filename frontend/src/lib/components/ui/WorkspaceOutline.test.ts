import { render, screen } from "@testing-library/svelte";
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
});
