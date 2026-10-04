import { render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it } from "vitest";

import TeacherGraphWorkspaceFrame from "./TeacherGraphWorkspaceFrame.svelte";

describe("TeacherGraphWorkspaceFrame", () => {
  it("renders the shared teacher graph shell with commandbar", () => {
    const { container } = render(TeacherGraphWorkspaceFrame, {
      props: {
        backHref: "/teaching/units",
        backLabel: "Zurück zu Lerneinheiten",
        title: "Programmieren mit Scratch",
        copy: "8 Phasen · 21 Module",
        embedded: true,
        commandBarActions: [
          { label: "Phase hinzufügen", href: "/ui-lab", active: true },
          { label: "Modul hinzufügen", href: "/ui-lab", active: false }
        ]
      }
    });

    expect(screen.getByRole("link", { name: "Zurück zu Lerneinheiten" })).toHaveAttribute("href", "/teaching/units");
    expect(screen.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeInTheDocument();
    expect(screen.getByText("Lernweg")).toBeInTheDocument();
    expect(screen.getByLabelText("Lernweg-Graph").parentElement).toHaveClass("teacher-flow-workspace--embedded");
    expect(container.querySelector(".teacher-graph-workspace-frame__commandbar")).toContainElement(
      screen.getByRole("toolbar", { name: "Graphwerkzeuge" })
    );
    expect(container.querySelector(".page-action-head")).not.toContainElement(
      screen.getByRole("toolbar", { name: "Graphwerkzeuge" })
    );
  });

  it("keeps graph context and inspector inside the graph-first surface", () => {
    const contextBar = createRawSnippet(() => ({
      render: () => '<section aria-label="Ausgewählte Phase">Phase 1</section>'
    }));
    const canvas = createRawSnippet(() => ({
      render: () => '<div data-testid="graph-canvas-content">Graph</div>'
    }));
    const inspector = createRawSnippet(() => ({
      render: () => '<aside aria-label="Phase bearbeiten">Inspector</aside>'
    }));

    const { container } = render(TeacherGraphWorkspaceFrame, {
      props: {
        backHref: "/teaching/units",
        backLabel: "Zurück zu Lerneinheiten",
        title: "Programmieren mit Scratch",
        copy: "1 Phase · 2 Module",
        commandBarActions: [],
        contextBar,
        contextOpen: true,
        inspectorOpen: true,
        canvas,
        inspector
      }
    });

    const frame = container.querySelector<HTMLElement>(".teacher-graph-workspace-frame");
    const workspace = screen.getByLabelText("Lernweg-Graph").closest<HTMLElement>(".teacher-flow-workspace");
    const context = screen.getByRole("region", { name: "Ausgewählte Phase" });

    expect(frame).toBeInTheDocument();
    expect(frame).toHaveClass("teacher-graph-workspace-frame--with-context");
    expect(frame).toContainElement(workspace);
    expect(context.closest(".teacher-flow-workspace__context")?.parentElement).toBe(workspace);
    expect(screen.getByTestId("graph-canvas-content").closest(".teacher-flow-workspace__canvas")?.parentElement).toBe(workspace);
    expect(frame).toContainElement(screen.getByRole("complementary", { name: "Phase bearbeiten" }));
  });

  it("does not reserve a mobile context row when no graph item is selected", () => {
    const contextBar = createRawSnippet(() => ({
      render: () => '<section aria-label="Ausgewählte Phase">Phase 1</section>'
    }));

    const { container } = render(TeacherGraphWorkspaceFrame, {
      props: {
        backHref: "/teaching/units",
        backLabel: "Zurück zu Lerneinheiten",
        title: "Programmieren mit Scratch",
        copy: "1 Phase · 2 Module",
        commandBarActions: [],
        contextBar,
        contextOpen: false
      }
    });

    expect(container.querySelector(".teacher-flow-workspace__context")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Lernweg-Graph").parentElement).not.toHaveClass(
      "teacher-flow-workspace--with-context"
    );
  });
});
