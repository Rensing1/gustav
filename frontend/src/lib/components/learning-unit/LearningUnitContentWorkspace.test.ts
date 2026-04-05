import { render } from "@testing-library/svelte";
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
      }
    ]
  }
];

describe("LearningUnitContentWorkspace", () => {
  it("uses a non-stretching vertical stack for pane items", () => {
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
        historyTaskId: null,
        history: [],
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
        onExitSubmissionWorkspace: () => {}
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
    expect(stack?.children).toHaveLength(2);
    expect(css).toMatch(/\.learning-unit-pane__stack\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;/s);
    expect(css).toMatch(/\.learning-unit-pane\s*\{[^}]*display:\s*grid;[^}]*grid-template-rows:\s*minmax\(0,\s*1fr\);/s);
    expect(css).not.toMatch(/\.learning-unit-pane\s*\{[^}]*min-height:\s*20rem;/s);
    expect(css).not.toMatch(/\.learning-unit-workspace-surface\s*\{[^}]*min-height:\s*100%;/s);
    expect(css).toMatch(/\.learning-unit-workspace-surface\s*\{[^}]*padding:\s*0\s+1\.3rem;/s);
    expect(css).toMatch(/\.learning-unit-pane-grid--single\s*\{[^}]*width:\s*min\(100%,\s*48rem\);[^}]*justify-self:\s*center;/s);
    expect(css).toMatch(/\.learning-work-item__title\s*\{[^}]*display:\s*flex;[^}]*align-items:\s*center;[^}]*min-height:\s*1\.4rem;/s);
    expect(css).not.toMatch(/\.learning-unit-toc__item--active\s*\{[^}]*font-weight:/s);
    expect(css).toMatch(/\.learning-unit-toc__item--active::before\s*\{[^}]*background:/s);
  });
});
