import { describe, expect, it } from "vitest";

import {
  LEARNING_UNIT_WORKSPACE_STORAGE_VERSION,
  learningUnitWorkspaceStorageKey,
  readLearningUnitWorkspaceState,
  serializeLearningUnitWorkspaceState
} from "./workspace-storage";

describe("learning unit workspace storage", () => {
  it("uses the stable per-course and per-unit storage key", () => {
    expect(learningUnitWorkspaceStorageKey("course-1", "unit-1")).toBe(
      "gustav.learning.unit-workspace:course-1:unit-1"
    );
  });

  it("returns normalized defaults when browser storage is unavailable", () => {
    const restored = readLearningUnitWorkspaceState({
      storage: null,
      courseId: "course-1",
      unitId: "unit-1",
      viewportWidth: 700,
      openableModuleIds: new Set(["module-open"])
    });

    expect(restored.modular).toMatchObject({
      view: "overview",
      openTabs: [],
      activeTab: null,
      tocOpen: false
    });
    expect(restored.linear).toMatchObject({
      splitView: false,
      tocOpen: false,
      activePane: "left"
    });
    expect(restored.layout.workspaceWidth).toBe(40.5);
  });

  it("normalizes versioned state and drops locked module tabs", () => {
    const storage = new Map<string, string>();
    storage.set(
      learningUnitWorkspaceStorageKey("course-1", "unit-1"),
      JSON.stringify({
        version: LEARNING_UNIT_WORKSPACE_STORAGE_VERSION,
        modular: {
          view: "content",
          openTabs: ["locked", "open"],
          activeTab: "locked",
          splitView: true,
          paneStacks: { left: ["task:1"], right: [] }
        },
        linear: {
          splitView: false,
          activePane: "right"
        },
        layout: {
          singlePaneWidth: 30,
          fontScale: 8
        }
      })
    );

    const restored = readLearningUnitWorkspaceState({
      storage,
      courseId: "course-1",
      unitId: "unit-1",
      viewportWidth: 1280,
      openableModuleIds: new Set(["open"])
    });

    expect(restored.modular.openTabs).toEqual(["open"]);
    expect(restored.modular.activeTab).toBe("open");
    expect(restored.modular.paneStacks?.left).toEqual([{ key: "task:1", expanded: true }]);
    expect(restored.linear.activePane).toBe("right");
    expect(restored.layout.workspaceWidth).toBe(48);
    expect(restored.layout.fontScale).toBe(4);
  });

  it("normalizes legacy modular-only state without a version wrapper", () => {
    const storage = new Map<string, string>();
    storage.set(
      learningUnitWorkspaceStorageKey("course-1", "unit-1"),
      JSON.stringify({
        view: "content",
        openTabs: ["open"],
        activeTab: "open"
      })
    );

    const restored = readLearningUnitWorkspaceState({
      storage,
      courseId: "course-1",
      unitId: "unit-1",
      viewportWidth: 1280,
      openableModuleIds: new Set(["open"])
    });

    expect(restored.modular.view).toBe("content");
    expect(restored.modular.openTabs).toEqual(["open"]);
    expect(restored.linear.splitView).toBe(false);
  });

  it("serializes the current storage version with modular, linear and layout state", () => {
    const serialized = JSON.parse(
      serializeLearningUnitWorkspaceState({
        modular: readLearningUnitWorkspaceState({
          storage: null,
          courseId: "course-1",
          unitId: "unit-1",
          viewportWidth: 1280,
          openableModuleIds: new Set()
        }).modular,
        linear: readLearningUnitWorkspaceState({
          storage: null,
          courseId: "course-1",
          unitId: "unit-1",
          viewportWidth: 1280,
          openableModuleIds: new Set()
        }).linear,
        layout: readLearningUnitWorkspaceState({
          storage: null,
          courseId: "course-1",
          unitId: "unit-1",
          viewportWidth: 1280,
          openableModuleIds: new Set()
        }).layout
      })
    );

    expect(serialized.version).toBe(LEARNING_UNIT_WORKSPACE_STORAGE_VERSION);
    expect(serialized.modular).toBeTruthy();
    expect(serialized.linear).toBeTruthy();
    expect(serialized.layout).toBeTruthy();
  });

  it("falls back to defaults for invalid JSON", () => {
    const storage = new Map<string, string>();
    storage.set(learningUnitWorkspaceStorageKey("course-1", "unit-1"), "{invalid");

    const restored = readLearningUnitWorkspaceState({
      storage,
      courseId: "course-1",
      unitId: "unit-1",
      viewportWidth: 1280,
      openableModuleIds: new Set(["open"])
    });

    expect(restored.modular.view).toBe("overview");
    expect(restored.modular.openTabs).toEqual([]);
  });
});
