import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import LearnerMaterialContext from "./LearnerMaterialContext.svelte";
import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";

const modules: LearnerMaterialContextModule[] = [
  {
    id: "module-current",
    title: "Grundlagen",
    current: true,
    closable: false,
    loaded: true,
    loading: false,
    error: null,
    items: [
      {
        key: "material:one",
        kind: "material",
        title: "Erste Quelle",
        position: 1,
        contextLabel: "Grundlagen",
        moduleId: "module-current",
        material: { id: "one", title: "Erste Quelle", kind: "markdown", body_md: "Vollständiger erster Inhalt." }
      },
      {
        key: "material:two",
        kind: "material",
        title: "Zweite Quelle",
        position: 2,
        contextLabel: "Grundlagen",
        moduleId: "module-current",
        material: { id: "two", title: "Zweite Quelle", kind: "markdown", body_md: "Vollständiger zweiter Inhalt." }
      },
      {
        key: "task:old",
        kind: "task",
        title: "Aufgabe 1",
        position: 3,
        contextLabel: "Grundlagen",
        moduleId: "module-current",
        task: { id: "old", instruction_md: "Begründe.", criteria: [], kind: "native", has_submission: true }
      }
    ]
  },
  {
    id: "module-extra",
    title: "Gegenposition",
    current: false,
    closable: true,
    loaded: true,
    loading: false,
    error: null,
    items: [
      {
        key: "material:extra",
        kind: "material",
        title: "Weitere Quelle",
        position: 1,
        contextLabel: "Gegenposition",
        moduleId: "module-extra",
        material: { id: "extra", title: "Weitere Quelle", kind: "markdown", body_md: "Inhalt aus dem geöffneten Modul." }
      }
    ]
  },
  {
    id: "module-empty",
    title: "Leeres Modul",
    current: false,
    closable: true,
    loaded: true,
    loading: false,
    error: null,
    items: []
  }
];

function props() {
  return {
    courseId: "course-1",
    modules,
    expandedModuleIds: ["module-extra", "module-empty"],
    expandedModuleMaterialKeys: { "module-extra": ["material:extra"] },
    expandedSubmissionModuleIds: [],
    expandedSubmissionKeys: [],
    historyByTask: {},
    historyStateByTask: {},
    focusedModuleId: null,
    closedModuleTitle: null,
    onToggleModule: vi.fn(),
    onToggleMaterial: vi.fn(),
    onToggleSubmissionGroup: vi.fn(),
    onToggleSubmission: vi.fn(),
    onOpenReference: vi.fn(),
    onCloseModule: vi.fn(),
    onUndoCloseModule: vi.fn()
  };
}

describe("LearnerMaterialContext", () => {
  it("shows only supplied opened modules with the current module first", async () => {
    const value = props();
    render(LearnerMaterialContext, { props: value });

    const context = screen.getByRole("region", { name: "Materialien" });
    const headings = within(context).getAllByRole("heading", { level: 4 });
    expect(headings.map((heading) => heading.textContent)).toEqual([
      expect.stringContaining("Grundlagen"),
      expect.stringContaining("Gegenposition"),
      expect.stringContaining("Leeres Modul")
    ]);
    expect(within(context).getByText("Aktuell")).toBeInTheDocument();
    expect(within(context).queryByText("Angeheftet")).not.toBeInTheDocument();
    expect(within(context).queryByText("Material suchen")).not.toBeInTheDocument();
    expect(within(context).queryByRole("button", { name: /anheften|lösen/i })).not.toBeInTheDocument();

    expect(within(context).queryByRole("button", { name: "Modul Grundlagen schließen" })).not.toBeInTheDocument();
    await fireEvent.click(within(context).getByRole("button", { name: "Modul Gegenposition schließen" }));
    expect(value.onCloseModule).toHaveBeenCalledWith("module-extra");
  });

  it("opens the first document by default and keeps multiple documents independently controllable", async () => {
    const value = props();
    render(LearnerMaterialContext, { props: value });

    expect(screen.getByText("Vollständiger erster Inhalt.")).toBeInTheDocument();
    expect(screen.queryByText("Vollständiger zweiter Inhalt.")).not.toBeInTheDocument();
    expect(screen.getByText("Inhalt aus dem geöffneten Modul.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Zweite Quelle ein- oder ausklappen" }));
    expect(value.onToggleMaterial).toHaveBeenCalledWith("module-current", "material:two");
    await fireEvent.click(screen.getByRole("button", { name: "Modul Gegenposition ein- oder ausklappen" }));
    expect(value.onToggleModule).toHaveBeenCalledWith("module-extra");
  });

  it("loads own submissions only when their module group is deliberately opened", async () => {
    const value = props();
    const { rerender } = render(LearnerMaterialContext, { props: value });

    const toggle = screen.getByRole("button", { name: "Eigene Abgaben in Grundlagen ein- oder ausklappen" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("article", { name: "Aufgabe 1" })).not.toBeInTheDocument();
    await fireEvent.click(toggle);
    expect(value.onToggleSubmissionGroup).toHaveBeenCalledWith("module-current");

    await rerender({
      ...value,
      expandedSubmissionModuleIds: ["module-current"],
      expandedSubmissionKeys: ["submission:old"],
      historyStateByTask: { old: "loaded" },
      historyByTask: {
        old: [{
          id: "submission-old",
          intent: "submit",
          attempt_nr: 2,
          kind: "text",
          created_at: "2026-08-06T10:00:00+00:00",
          analysis_status: "completed",
          text_body: "Meine frühere Begründung."
        }]
      }
    });

    expect(screen.getByText("Meine frühere Begründung.")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Aufgabe 1 ein- oder ausklappen" }));
    expect(value.onToggleSubmission).toHaveBeenCalledWith("submission:old");
  });

  it("keeps empty modules visible and offers an accessible local undo", async () => {
    const value = { ...props(), closedModuleTitle: "Gegenposition" };
    render(LearnerMaterialContext, { props: value });

    expect(screen.getByText("Keine Materialien")).toBeInTheDocument();
    const status = screen.getByRole("status");
    expect(within(status).getByText("Modul „Gegenposition“ geschlossen.")).toBeInTheDocument();
    await fireEvent.click(within(status).getByRole("button", { name: "Rückgängig" }));
    expect(value.onUndoCloseModule).toHaveBeenCalledOnce();
  });

  it("expresses the material hierarchy as a tree with actions owned by their level", async () => {
    const value = props();
    const { container, rerender } = render(LearnerMaterialContext, { props: value });

    const currentModule = container.querySelector('[data-context-module-id="module-current"]');
    const extraModule = container.querySelector('[data-context-module-id="module-extra"]');
    expect(currentModule).not.toBeNull();
    expect(extraModule).not.toBeNull();
    expect(currentModule?.querySelector(":scope > .learner-material-context__module-header .learner-tree-chevron")).not.toBeNull();
    expect(currentModule?.querySelector(":scope > .learner-material-context__module-body.learner-material-context__tree-children")).not.toBeNull();
    expect(extraModule?.querySelector(":scope > .learner-material-context__module-header .learner-tree-chevron")).not.toBeNull();
    expect(within(extraModule as HTMLElement).getByRole("button", { name: "Modul Gegenposition schließen" })).toBeInTheDocument();

    const material = screen.getByRole("article", { name: "Erste Quelle" });
    expect(material.closest(".learner-material-context__tree-item--document")).not.toBeNull();
    expect(material.querySelector(".learner-tree-chevron")).not.toBeNull();
    expect(within(material).getByRole("button", { name: "Erste Quelle groß lesen" })).toBeInTheDocument();
    expect(within(material).queryByRole("button", { name: /schließen/i })).not.toBeInTheDocument();

    const submissionsToggle = screen.getByRole("button", { name: "Eigene Abgaben in Grundlagen ein- oder ausklappen" });
    expect(submissionsToggle.querySelector(".learner-tree-chevron")).not.toBeNull();
    expect(within(submissionsToggle).queryByTitle("Großansicht")).not.toBeInTheDocument();
    await fireEvent.click(submissionsToggle);

    await rerender({
      ...value,
      expandedSubmissionModuleIds: ["module-current"],
      historyStateByTask: { old: "loaded" },
      historyByTask: {
        old: [{
          id: "submission-old",
          intent: "submit",
          attempt_nr: 1,
          kind: "text",
          created_at: "2026-08-06T10:00:00+00:00",
          analysis_status: "completed",
          text_body: "Begründung"
        }]
      }
    });

    const submission = screen.getByRole("article", { name: "Aufgabe 1" });
    expect(submission.closest(".learner-material-context__tree-item--submission")).not.toBeNull();
    expect(within(submission).getByRole("button", { name: "Aufgabe 1 groß lesen" })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[+−]/);
  });
});
