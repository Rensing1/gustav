import { render, screen } from "@testing-library/svelte";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import LearningUnitContentWorkspace from "./LearningUnitContentWorkspace.svelte";
import type { ContentGroup } from "$lib/learning-unit/workspace";

const contentGroups: ContentGroup[] = [
  {
    id: "group-1",
    title: null,
    items: [
      {
        key: "material:1",
        kind: "material",
        title: "Was tut die Europäische Union für mich?",
        position: 1,
        contextLabel: null,
        material: {
          id: "material-1",
          title: "Was tut die Europäische Union für mich?",
          kind: "markdown",
          body_md: "Material"
        }
      },
      {
        key: "task:1",
        kind: "task",
        title: "Aufgabe 1",
        position: 2,
        contextLabel: null,
        task: {
          id: "task-1",
          instruction_md: "Erkläre den Zusammenhang.",
          criteria: [],
          kind: "native"
        }
      },
      {
        key: "task:2",
        kind: "task",
        title: "Aufgabe 2",
        position: 3,
        contextLabel: null,
        task: {
          id: "task-2",
          instruction_md: "Vergleiche zwei Positionen.",
          criteria: [],
          kind: "native"
        }
      }
    ]
  }
];

describe("LearningUnitContentWorkspace", () => {
  it("uses a non-stretching vertical stack for pane items", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const appCss = readFileSync(path.resolve(currentDir, "../../styles/app.css"), "utf8");
    const designSystemCss = readFileSync(path.resolve(currentDir, "../../styles/design-system.css"), "utf8");
    const { container } = render(LearningUnitContentWorkspace, {
      props: {
        titleLabel: "",
        title: "",
        meta: null,
        courseId: "course-1",
        unitType: "linear",
        tocOpen: false,
        splitView: false,
        activePane: "left",
        visiblePaneIds: ["left"],
        contentGroups,
        paneItems: {
          left: contentGroups[0].items.map((item) => ({ item, expanded: false })),
          right: []
        },
        historyByTask: {},
        submittedTaskId: null,
        submissionMessage: null,
        submissionErrorTaskId: null,
        submissionErrorMessage: null,
        submissionFocusByPane: { left: null, right: null },
        submissionModeByPane: { left: null, right: null },
        showSplitToggle: false,
        layoutMenuEnabled: false,
        itemDomId: (_paneId: "left" | "right", itemKey: string) => itemKey,
        onToggleToc: () => {},
        onToggleSplitView: () => {},
        onResetLayout: () => {},
        onUpdateTocWidth: () => {},
        onPreviewWorkspaceWidth: () => {},
        onCommitWorkspaceWidth: () => {},
        onPreviewFontScale: () => {},
        onCommitFontScale: () => {},
        onUpdateSplitRatio: () => {},
        onUpdateTocGap: () => {},
        onUpdatePaneGap: () => {},
        onSetActivePane: () => {},
        onOpenItem: () => {},
        onToggleItem: () => {},
        onEnterSubmissionWorkspace: () => {},
        onEnterUploadWorkspace: () => {},
        onExitSubmissionWorkspace: () => {},
        onToggleReviewPanel: () => {}
      }
    });

    const stack = container.querySelector(".learning-unit-pane__stack");
    const pane = container.querySelector(".learning-unit-pane");
    const surface = container.querySelector(".learning-unit-workspace-surface");
    const frameHeader = container.querySelector(".workspace-frame-header");
    expect(stack).not.toBeNull();
    expect(pane).not.toBeNull();
    expect(surface).not.toBeNull();
    expect(frameHeader).toBeNull();
    expect(stack?.children).toHaveLength(3);
    expect(appCss).toMatch(/\.learning-unit-pane__stack\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;/s);
    expect(appCss).toMatch(/\.learning-unit-pane\s*\{[^}]*display:\s*grid;[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\);/s);
    expect(appCss).not.toMatch(/\.learning-unit-pane\s*\{[^}]*min-height:\s*20rem;/s);
    expect(appCss).not.toMatch(/\.learning-unit-workspace-surface\s*\{[^}]*min-height:\s*100%;/s);
    expect(appCss).not.toMatch(/\.learning-unit-pane--workspace-mode\s*\{/s);
    expect(appCss).not.toMatch(/\.learning-unit-workspace-surface--focused\s*\{/s);
    expect(appCss).not.toMatch(/\.learning-unit-pane__stack--workspace-mode\s*\{/s);
    expect(appCss).toMatch(/\.learning-unit-pane-grid--single\s*\{[^}]*width:\s*100%;[^}]*justify-self:\s*stretch;/s);
    expect(appCss).toMatch(/\.learning-work-item__title\s*\{[^}]*display:\s*flex;[^}]*align-items:\s*center;[^}]*min-height:\s*1\.4rem;/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.workspace-outline\s*\{[^}]*position:\s*sticky;[^}]*top:\s*1rem;[^}]*padding:\s*0;[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-unit-workspace-surface\s*\{[^}]*padding:\s*0;[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
  });

  it("keeps other pane items visible even when one task editor is open", () => {
    const { container } = render(LearningUnitContentWorkspace, {
      props: {
        titleLabel: "",
        title: "",
        meta: null,
        courseId: "course-1",
        unitType: "linear",
        tocOpen: false,
        splitView: false,
        activePane: "left",
        visiblePaneIds: ["left"],
        contentGroups,
        paneItems: {
          left: contentGroups[0].items.map((item) => ({ item, expanded: true })),
          right: []
        },
        historyByTask: {},
        submittedTaskId: null,
        submissionMessage: null,
        submissionErrorTaskId: null,
        submissionErrorMessage: null,
        submissionFocusByPane: { left: "task:1", right: null },
        submissionModeByPane: { left: "text", right: null },
        showSplitToggle: false,
        layoutMenuEnabled: false,
        itemDomId: (_paneId: "left" | "right", itemKey: string) => itemKey,
        onToggleToc: () => {},
        onToggleSplitView: () => {},
        onResetLayout: () => {},
        onUpdateTocWidth: () => {},
        onPreviewWorkspaceWidth: () => {},
        onCommitWorkspaceWidth: () => {},
        onPreviewFontScale: () => {},
        onCommitFontScale: () => {},
        onUpdateSplitRatio: () => {},
        onUpdateTocGap: () => {},
        onUpdatePaneGap: () => {},
        onSetActivePane: () => {},
        onOpenItem: () => {},
        onToggleItem: () => {},
        onEnterSubmissionWorkspace: () => {},
        onEnterUploadWorkspace: () => {},
        onExitSubmissionWorkspace: () => {},
        onToggleReviewPanel: () => {}
      }
    });

    expect(screen.getByText("Was tut die Europäische Union für mich?")).toBeInTheDocument();
    expect(screen.getAllByText("Aufgabe 1").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Bearbeitung schließen" })).toBeInTheDocument();
    expect(container.querySelectorAll(".learning-work-item")).toHaveLength(3);
  });

  it("passes submission history only to the matching task card", () => {
    render(LearningUnitContentWorkspace, {
      props: {
        titleLabel: "",
        title: "",
        meta: null,
        courseId: "course-1",
        unitType: "linear",
        tocOpen: false,
        splitView: false,
        activePane: "left",
        visiblePaneIds: ["left"],
        contentGroups,
        paneItems: {
          left: contentGroups[0].items.map((item) => ({ item, expanded: true })),
          right: []
        },
        historyByTask: {
          "task-1": [
            {
              id: "submission-1",
              attempt_nr: 1,
              kind: "text",
              intent: "submit",
              created_at: "2026-04-07T10:35:29+00:00",
              analysis_status: "completed",
              text_body: "Meine Lösung"
            }
          ]
        },
        submittedTaskId: null,
        submissionMessage: null,
        submissionErrorTaskId: null,
        submissionErrorMessage: null,
        submissionFocusByPane: { left: null, right: null },
        submissionModeByPane: { left: null, right: null },
        reviewPanelOpenByTask: {},
        showSplitToggle: false,
        layoutMenuEnabled: false,
        itemDomId: (_paneId: "left" | "right", itemKey: string) => itemKey,
        onToggleToc: () => {},
        onToggleSplitView: () => {},
        onResetLayout: () => {},
        onUpdateTocWidth: () => {},
        onPreviewWorkspaceWidth: () => {},
        onCommitWorkspaceWidth: () => {},
        onPreviewFontScale: () => {},
        onCommitFontScale: () => {},
        onUpdateSplitRatio: () => {},
        onUpdateTocGap: () => {},
        onUpdatePaneGap: () => {},
        onSetActivePane: () => {},
        onOpenItem: () => {},
        onToggleItem: () => {},
        onEnterSubmissionWorkspace: () => {},
        onEnterUploadWorkspace: () => {},
        onExitSubmissionWorkspace: () => {},
        onToggleReviewPanel: () => {}
      }
    });

    expect(screen.getAllByRole("button", { name: "Erneut bearbeiten" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Meine Abgabe" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Aufgabe beginnen" })).toHaveLength(1);
  });

  it("marks all items of open modular groups in the outline", () => {
    render(LearningUnitContentWorkspace, {
      props: {
        titleLabel: "",
        title: "",
        meta: null,
        courseId: "course-1",
        unitType: "modular",
        tocOpen: true,
        splitView: false,
        activePane: "left",
        visiblePaneIds: ["left"],
        contentGroups: [
          {
            id: "module-1",
            title: "Fachbegriffe",
            items: [
              { key: "material:1", kind: "material", title: "Was ist Programmieren?", position: 1, contextLabel: "Fachbegriffe", material: { id: "material-1", title: "Was ist Programmieren?", kind: "markdown", body_md: "Material" } },
              { key: "task:1", kind: "task", title: "Aufgabe 1", position: 2, contextLabel: "Fachbegriffe", task: { id: "task-1", instruction_md: "Aufgabe", criteria: [], kind: "native" } }
            ]
          },
          {
            id: "module-2",
            title: "Algorithmen",
            items: [
              { key: "material:2", kind: "material", title: "Schulbuch", position: 1, contextLabel: "Algorithmen", material: { id: "material-2", title: "Schulbuch", kind: "markdown", body_md: "Material" } }
            ]
          }
        ],
        paneItems: {
          left: [],
          right: []
        },
        historyByTask: {},
        submittedTaskId: null,
        submissionMessage: null,
        submissionErrorTaskId: null,
        submissionErrorMessage: null,
        submissionFocusByPane: { left: null, right: null },
        submissionModeByPane: { left: null, right: null },
        showSplitToggle: false,
        layoutMenuEnabled: false,
        itemDomId: (_paneId: "left" | "right", itemKey: string) => itemKey,
        onToggleToc: () => {},
        onToggleSplitView: () => {},
        onResetLayout: () => {},
        onUpdateTocWidth: () => {},
        onPreviewWorkspaceWidth: () => {},
        onCommitWorkspaceWidth: () => {},
        onPreviewFontScale: () => {},
        onCommitFontScale: () => {},
        onUpdateSplitRatio: () => {},
        onUpdateTocGap: () => {},
        onUpdatePaneGap: () => {},
        onSetActivePane: () => {},
        onOpenItem: () => {},
        onToggleItem: () => {},
        onEnterSubmissionWorkspace: () => {},
        onEnterUploadWorkspace: () => {},
        onExitSubmissionWorkspace: () => {},
        onToggleReviewPanel: () => {}
      }
    });

    expect(screen.getByRole("button", { name: "Was ist Programmieren?" })).toHaveClass("workspace-outline__item--active");
    expect(screen.getByRole("button", { name: "Aufgabe 1" })).toHaveClass("workspace-outline__item--active");
    expect(screen.getByRole("button", { name: "Schulbuch" })).toHaveClass("workspace-outline__item--active");
  });

  it("renders modular groups as separate module blocks with materials before tasks", () => {
    const cssPath = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "../../styles/app.css"
    );
    const css = readFileSync(cssPath, "utf8");
    const { container } = render(LearningUnitContentWorkspace, {
      props: {
        titleLabel: "",
        title: "",
        meta: null,
        courseId: "course-1",
        unitType: "modular",
        tocOpen: false,
        splitView: false,
        activePane: "left",
        visiblePaneIds: ["left"],
        contentGroups: [
          {
            id: "module-1",
            title: "Fachbegriffe",
            items: [
              {
                key: "material:1",
                kind: "material",
                title: "Was ist Programmieren?",
                position: 1,
                contextLabel: "Fachbegriffe",
                moduleId: "module-1",
                material: { id: "material-1", title: "Was ist Programmieren?", kind: "markdown", body_md: "Material" }
              },
              {
                key: "task:1",
                kind: "task",
                title: "Aufgabe 1",
                position: 2,
                contextLabel: "Fachbegriffe",
                moduleId: "module-1",
                task: { id: "task-1", instruction_md: "Aufgabe", criteria: [], kind: "native" }
              }
            ]
          },
          {
            id: "module-2",
            title: "Algorithmen",
            items: [
              {
                key: "material:2",
                kind: "material",
                title: "Schulbuch",
                position: 1,
                contextLabel: "Algorithmen",
                moduleId: "module-2",
                material: { id: "material-2", title: "Schulbuch", kind: "markdown", body_md: "Material" }
              }
            ]
          }
        ],
        paneItems: {
          left: [
            {
              item: {
                key: "material:1",
                kind: "material",
                title: "Was ist Programmieren?",
                position: 1,
                contextLabel: "Fachbegriffe",
                moduleId: "module-1",
                material: { id: "material-1", title: "Was ist Programmieren?", kind: "markdown", body_md: "Material" }
              },
              expanded: true
            },
            {
              item: {
                key: "task:1",
                kind: "task",
                title: "Aufgabe 1",
                position: 2,
                contextLabel: "Fachbegriffe",
                moduleId: "module-1",
                task: { id: "task-1", instruction_md: "Aufgabe", criteria: [], kind: "native" }
              },
              expanded: true
            },
            {
              item: {
                key: "material:2",
                kind: "material",
                title: "Schulbuch",
                position: 1,
                contextLabel: "Algorithmen",
                moduleId: "module-2",
                material: { id: "material-2", title: "Schulbuch", kind: "markdown", body_md: "Material" }
              },
              expanded: true
            }
          ],
          right: []
        },
        historyByTask: {},
        submittedTaskId: null,
        submissionMessage: null,
        submissionErrorTaskId: null,
        submissionErrorMessage: null,
        submissionFocusByPane: { left: null, right: null },
        submissionModeByPane: { left: null, right: null },
        reviewPanelOpenByTask: {},
        showSplitToggle: false,
        layoutMenuEnabled: false,
        itemDomId: (_paneId: "left" | "right", itemKey: string) => itemKey,
        onToggleToc: () => {},
        onToggleSplitView: () => {},
        onResetLayout: () => {},
        onUpdateTocWidth: () => {},
        onPreviewWorkspaceWidth: () => {},
        onCommitWorkspaceWidth: () => {},
        onPreviewFontScale: () => {},
        onCommitFontScale: () => {},
        onUpdateSplitRatio: () => {},
        onUpdateTocGap: () => {},
        onUpdatePaneGap: () => {},
        onSetActivePane: () => {},
        onOpenItem: () => {},
        onToggleItem: () => {},
        onEnterSubmissionWorkspace: () => {},
        onEnterUploadWorkspace: () => {},
        onExitSubmissionWorkspace: () => {},
        onToggleReviewPanel: () => {}
      }
    });

    const modules = container.querySelectorAll(".learning-unit-module");
    expect(modules).toHaveLength(2);
    expect(screen.getAllByText("Materialien")).toHaveLength(2);
    expect(screen.getAllByText("Aufgaben")).toHaveLength(2);
    expect(screen.getByText("Fachbegriffe")).toBeInTheDocument();
    expect(screen.getByText("Algorithmen")).toBeInTheDocument();

    const firstModule = modules[0];
    const materialsSection = firstModule?.querySelector(".learning-unit-module__materials");
    const tasksSection = firstModule?.querySelector(".learning-unit-module__tasks");

    expect(materialsSection?.textContent).toContain("Was ist Programmieren?");
    expect(tasksSection?.textContent).toContain("Aufgabe 1");
    expect(
      materialsSection &&
        tasksSection &&
        Boolean(materialsSection.compareDocumentPosition(tasksSection) & Node.DOCUMENT_POSITION_FOLLOWING)
    ).toBe(true);
    expect(css).not.toMatch(/\.learning-unit-module\s*\{[^}]*border-bottom:/s);
    expect(css).not.toMatch(/\.learning-unit-module\s*\{[^}]*background:/s);
    expect(css).not.toMatch(/\.learning-unit-module\s*\{[^}]*box-shadow:/s);
    expect(css).toMatch(
      /\.learning-unit-pane__stack--modules\s*\{[^}]*gap:\s*var\(--space-7\);[^}]*padding:\s*var\(--space-5\)\s+0\s+var\(--space-6\);/s
    );
    expect(css).toMatch(
      /\.learning-unit-module\s*\{[^}]*gap:\s*var\(--space-5\);[^}]*padding:\s*0\s+0\s+var\(--space-5\);/s
    );
    expect(css).toMatch(/\.learning-unit-module__materials,\s*\.learning-unit-module__tasks\s*\{[^}]*gap:\s*var\(--space-4\);/s);
    expect(css).toMatch(
      /\.learning-unit-module__tasks\s*\{[^}]*margin-top:\s*var\(--space-6\);/s
    );
    expect(css).toMatch(/\.learning-unit-module__section-body\s*\{[^}]*gap:\s*var\(--space-4\);/s);
  });

  it("omits the materials section when a module has no materials", () => {
    const { container } = render(LearningUnitContentWorkspace, {
      props: {
        titleLabel: "Inhalte",
        title: "Testeinheit",
        meta: null,
        courseId: "course-1",
        unitType: "modular",
        tocOpen: true,
        splitView: false,
        activePane: "left",
        visiblePaneIds: ["left"],
        contentGroups: [
          {
            id: "module-empty",
            title: "Ohne Material",
            items: [
              {
                key: "module-empty-task",
                kind: "task",
                position: 0,
                moduleId: "module-empty",
                title: "Aufgabe 1",
                contextLabel: null,
                task: {
                  id: "task-empty",
                  kind: "native",
                  instruction_md: "Arbeite an der Aufgabe.",
                  criteria: []
                }
              }
            ]
          }
        ],
        paneItems: {
          left: [
            {
              item: {
                key: "module-empty-task",
                kind: "task",
                position: 0,
                moduleId: "module-empty",
                title: "Aufgabe 1",
                contextLabel: null,
                task: {
                  id: "task-empty",
                  kind: "native",
                  instruction_md: "Arbeite an der Aufgabe.",
                  criteria: []
                }
              },
              expanded: true
            }
          ],
          right: []
        },
        historyByTask: {},
        submittedTaskId: null,
        submissionMessage: null,
        submissionErrorTaskId: null,
        submissionErrorMessage: null,
        feedbackPendingTaskId: null,
        feedbackStatusTaskId: null,
        feedbackStatusMessage: null,
        pendingSubmissionIntent: null,
        submissionFocusByPane: { left: null, right: null },
        submissionModeByPane: { left: null, right: null },
        reviewPanelOpenByTask: {},
        showSplitToggle: false,
        layoutMenuEnabled: false,
        tocWidth: 16.25,
        workspaceWidth: 112,
        splitRatio: 50,
        tocGap: 1.1,
        paneGap: 1.1,
        fontScale: 1,
        onSubmitUploadFeedback: async () => {},
        itemDomId: () => "dom-id",
        moduleId: null,
        enhanceTaskForm: null,
        onToggleToc: () => {},
        onToggleSplitView: () => {},
        onResetLayout: () => {},
        onUpdateTocWidth: () => {},
        onPreviewWorkspaceWidth: () => {},
        onCommitWorkspaceWidth: () => {},
        onPreviewFontScale: () => {},
        onCommitFontScale: () => {},
        onUpdateSplitRatio: () => {},
        onUpdateTocGap: () => {},
        onUpdatePaneGap: () => {},
        onSetActivePane: () => {},
        onOpenItem: () => {},
        onToggleItem: () => {},
        onEnterSubmissionWorkspace: () => {},
        onEnterUploadWorkspace: () => {},
        onExitSubmissionWorkspace: () => {},
        onToggleReviewPanel: () => {}
      }
    });

    const module = container.querySelector(".learning-unit-module");
    expect(module?.textContent).toContain("Ohne Material");
    expect(module?.querySelector(".learning-unit-module__materials")).toBeNull();
    expect(module?.querySelector(".learning-unit-module__tasks")).not.toBeNull();
    expect(screen.queryByText("Materialien")).toBeNull();
    expect(screen.getByText("Aufgaben")).toBeInTheDocument();
  });
});
