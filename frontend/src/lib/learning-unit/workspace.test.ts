import { describe, expect, it } from "vitest";

import {
  emptyReviewFocus,
  emptySubmissionFocus,
  reconcileModularWorkspaceState,
  reopenMaterialEntries,
  setPaneReviewFocus,
  togglePaneReviewFocus,
  togglePaneSubmissionFocus,
  type LearningContentItem,
  type LearningUnitViewState,
  type ModularWorkspaceSnapshot,
  type PaneStackEntry
} from "./workspace";

describe("workspace helpers", () => {
  it("reopens only material entries for the targeted modules", () => {
    const entries: PaneStackEntry[] = [
      { key: "material:1", expanded: false },
      { key: "task:1", expanded: false },
      { key: "material:2", expanded: false }
    ];
    const items: LearningContentItem[] = [
      {
        key: "material:1",
        kind: "material",
        title: "Material 1",
        position: 1,
        contextLabel: null,
        moduleId: "module-1"
      },
      {
        key: "task:1",
        kind: "task",
        title: "Aufgabe 1",
        position: 2,
        contextLabel: null,
        moduleId: "module-1"
      },
      {
        key: "material:2",
        kind: "material",
        title: "Material 2",
        position: 1,
        contextLabel: null,
        moduleId: "module-2"
      }
    ];

    const reopened = reopenMaterialEntries(entries, items, ["module-1"]);

    expect(reopened).toEqual([
      { key: "material:1", expanded: true },
      { key: "task:1", expanded: false },
      { key: "material:2", expanded: false }
    ]);
  });

  it("toggles the same editor target closed and clears review in the same pane", () => {
    const firstOpen = togglePaneSubmissionFocus(
      emptySubmissionFocus(),
      { left: "task:1", right: null },
      "left",
      "task:1",
      "text"
    );

    expect(firstOpen.submissionFocus.left).toEqual({ itemKey: "task:1", mode: "text" });
    expect(firstOpen.reviewFocus.left).toBeNull();

    const closed = togglePaneSubmissionFocus(
      firstOpen.submissionFocus,
      firstOpen.reviewFocus,
      "left",
      "task:1",
      "text"
    );

    expect(closed.submissionFocus.left).toEqual({ itemKey: null, mode: null });
    expect(closed.reviewFocus.left).toBeNull();
  });

  it("opens review exclusively in the same pane without affecting the other pane", () => {
    const initialSubmissionFocus = {
      left: { itemKey: "task:1", mode: "text" as const },
      right: { itemKey: "task:2", mode: "upload" as const }
    };
    const initialReviewFocus = emptyReviewFocus();

    const next = togglePaneReviewFocus(
      initialSubmissionFocus,
      initialReviewFocus,
      "left",
      "task:1"
    );

    expect(next.submissionFocus.left).toEqual({ itemKey: null, mode: null });
    expect(next.reviewFocus.left).toBe("task:1");
    expect(next.submissionFocus.right).toEqual({ itemKey: "task:2", mode: "upload" });
    expect(next.reviewFocus.right).toBeNull();
  });

  it("closes the same review target on a second click", () => {
    const opened = setPaneReviewFocus(
      emptySubmissionFocus(),
      emptyReviewFocus(),
      "left",
      "task:3"
    );

    const closed = togglePaneReviewFocus(
      opened.submissionFocus,
      opened.reviewFocus,
      "left",
      "task:3"
    );

    expect(closed.reviewFocus.left).toBeNull();
    expect(closed.submissionFocus.left).toEqual({ itemKey: null, mode: null });
  });

  it("drops locked modules from the modular workspace and falls back to overview when no tab survives", () => {
    const workspace: ModularWorkspaceSnapshot = {
      view: "content",
      openTabs: ["module-a", "module-b"],
      activeTab: "module-b"
    };

    expect(
      reconcileModularWorkspaceState(workspace, {
        moduleOrder: ["module-a", "module-b", "module-c"],
        openableModuleIds: new Set(["module-c"]),
        requestedView: "content",
        requestedModuleId: "module-b"
      })
    ).toEqual({
      view: "overview",
      openTabs: [],
      activeTab: null
    });
  });

  it("keeps content view when the requested module remains openable and orders tabs by graph order", () => {
    const workspace: ModularWorkspaceSnapshot = {
      view: "content",
      openTabs: ["module-b", "module-a"],
      activeTab: "module-b"
    };

    expect(
      reconcileModularWorkspaceState(workspace, {
        moduleOrder: ["module-a", "module-b", "module-c"],
        openableModuleIds: new Set(["module-a", "module-b", "module-c"]),
        requestedView: "content",
        requestedModuleId: "module-b"
      })
    ).toEqual({
      view: "content",
      openTabs: ["module-a", "module-b"],
      activeTab: "module-b"
    });
  });

  it("prioritizes an explicit overview request over stale local content state", () => {
    const workspace: ModularWorkspaceSnapshot = {
      view: "content",
      openTabs: ["module-a"],
      activeTab: "module-a"
    };

    expect(
      reconcileModularWorkspaceState(workspace, {
        moduleOrder: ["module-a"],
        openableModuleIds: new Set(["module-a"]),
        requestedView: "overview",
        requestedModuleId: null
      })
    ).toEqual({
      view: "overview",
      openTabs: ["module-a"],
      activeTab: "module-a"
    });
  });
});
