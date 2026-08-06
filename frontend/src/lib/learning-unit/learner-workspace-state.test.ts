import { describe, expect, it } from "vitest";

import {
  defaultLearnerWorkspaceState,
  LEARNER_WORKSPACE_STORAGE_VERSION,
  learnerWorkspaceStorageKeys,
  normalizeLearnerWorkspaceState,
  readLearnerWorkspaceState,
  serializeLearnerWorkspacePersistentState,
  serializeLearnerWorkspaceTabState,
  type LearnerWorkspaceState
} from "./learner-workspace-state";

describe("learner workspace state", () => {
  it("uses version 5 for opened-module context disclosures", () => {
    expect(LEARNER_WORKSPACE_STORAGE_VERSION).toBe(5);
    expect(defaultLearnerWorkspaceState().context).toEqual({
      compactSurface: "task",
      expandedContextModuleIds: [],
      expandedModuleMaterialKeys: {},
      expandedSubmissionModuleIds: [],
      expandedSubmissionKeys: [],
      readingReferenceKey: null,
      focusedModuleId: null,
      bookScrollTop: 0,
      workScrollTop: 0,
      readerScrollTop: 0
    });
  });

  it("uses learner, course and unit in both storage keys", () => {
    expect(learnerWorkspaceStorageKeys("student/sub", "course-1", "unit-1")).toEqual({
      persistent: "gustav.learning.workspace:student%2Fsub:course-1:unit-1",
      tab: "gustav.learning.workspace:student%2Fsub:course-1:unit-1:tab"
    });
    expect(learnerWorkspaceStorageKeys(null, "course-1", "unit-1")).toBeNull();
  });

  it("stores opened modules persistently and reading state only in the current tab", () => {
    const state: LearnerWorkspaceState = {
      ...defaultLearnerWorkspaceState(),
      surface: "task",
      openedModuleIds: ["module-a", "module-b"],
      activeTask: {
        itemKey: "task:task-a",
        taskId: "task-a",
        moduleId: "module-a",
        status: "editing",
        editorMode: "text"
      },
      context: {
        compactSurface: "materials",
        expandedContextModuleIds: ["module-a", "module-b"],
        expandedModuleMaterialKeys: { "module-b": ["material:material-b"] },
        expandedSubmissionModuleIds: ["module-b"],
        expandedSubmissionKeys: ["submission:task-b"],
        readingReferenceKey: "material:material-b",
        focusedModuleId: "module-b",
        bookScrollTop: 420,
        workScrollTop: 180,
        readerScrollTop: 75
      },
      returnPosition: { moduleId: "module-a", scrollY: 640, focusId: "task-row-task-a" }
    };

    const persistent = JSON.parse(serializeLearnerWorkspacePersistentState(state));
    const tab = JSON.parse(serializeLearnerWorkspaceTabState(state));

    expect(persistent).toEqual({
      version: 5,
      openedModuleIds: ["module-a", "module-b"],
      preferences: { navigationVisible: true, fontSize: "standard" }
    });
    expect(tab.activeTask.taskId).toBe("task-a");
    expect(tab.context).toMatchObject({
      compactSurface: "materials",
      expandedContextModuleIds: ["module-a", "module-b"],
      expandedModuleMaterialKeys: { "module-b": ["material:material-b"] },
      expandedSubmissionModuleIds: ["module-b"],
      expandedSubmissionKeys: ["submission:task-b"],
      readingReferenceKey: "material:material-b",
      focusedModuleId: "module-b"
    });
  });

  it("keeps only accessible opened modules and their disclosure state", () => {
    const normalized = normalizeLearnerWorkspaceState(
      {
        openedModuleIds: ["module-open", "module-locked"],
        context: {
          expandedContextModuleIds: ["module-open", "module-locked"],
          expandedModuleMaterialKeys: {
            "module-open": ["material:allowed", "material:missing"],
            "module-locked": ["material:locked"]
          },
          expandedSubmissionModuleIds: ["module-open", "module-locked"],
          expandedSubmissionKeys: ["submission:allowed", "submission:locked"],
          focusedModuleId: "module-locked"
        }
      },
      {
        openableModuleIds: new Set(["module-open"]),
        accessibleReferenceKeys: new Set(["material:allowed", "submission:allowed"])
      }
    );

    expect(normalized.openedModuleIds).toEqual(["module-open"]);
    expect(normalized.context.expandedContextModuleIds).toEqual(["module-open"]);
    expect(normalized.context.expandedModuleMaterialKeys).toEqual({
      "module-open": ["material:allowed"]
    });
    expect(normalized.context.expandedSubmissionModuleIds).toEqual(["module-open"]);
    expect(normalized.context.expandedSubmissionKeys).toEqual(["submission:allowed"]);
    expect(normalized.context.focusedModuleId).toBeNull();
  });

  it("preserves an active task while the graph is used as material selection", () => {
    const normalized = normalizeLearnerWorkspaceState(
      {
        surface: "graph",
        openedModuleIds: ["module-open"],
        activeTask: {
          itemKey: "task:task-open",
          taskId: "task-open",
          moduleId: "module-open",
          status: "editing",
          editorMode: "upload"
        }
      },
      {
        openableModuleIds: new Set(["module-open"]),
        accessibleTaskKeys: new Set(["task:task-open"])
      }
    );

    expect(normalized.surface).toBe("graph");
    expect(normalized.activeTask?.taskId).toBe("task-open");
  });

  it("keeps disclosure state for released sections in a linear unit", () => {
    const normalized = normalizeLearnerWorkspaceState(
      {
        context: {
          expandedContextModuleIds: ["section-current", "section-open", "section-locked"],
          expandedModuleMaterialKeys: {
            "section-open": ["material:open"],
            "section-locked": ["material:locked"]
          },
          expandedSubmissionModuleIds: ["section-open"],
          expandedSubmissionKeys: ["submission:task-open"]
        }
      },
      {
        openableModuleIds: new Set(),
        accessibleContextModuleIds: new Set(["section-current", "section-open"]),
        accessibleReferenceKeys: new Set(["material:open", "submission:task-open"])
      }
    );

    expect(normalized.context.expandedContextModuleIds).toEqual(["section-current", "section-open"]);
    expect(normalized.context.expandedModuleMaterialKeys).toEqual({ "section-open": ["material:open"] });
    expect(normalized.context.expandedSubmissionModuleIds).toEqual(["section-open"]);
    expect(normalized.context.expandedSubmissionKeys).toEqual(["submission:task-open"]);
  });

  it("drops an inaccessible active task and its reader", () => {
    const normalized = normalizeLearnerWorkspaceState(
      {
        surface: "task",
        openedModuleIds: ["module-open"],
        activeTask: {
          itemKey: "task:locked-task",
          taskId: "locked-task",
          moduleId: "module-locked",
          status: "editing",
          editorMode: "upload"
        },
        context: {
          readingReferenceKey: "material:locked"
        }
      },
      {
        openableModuleIds: new Set(["module-open"]),
        accessibleTaskKeys: new Set(["task:other"]),
        accessibleReferenceKeys: new Set(["material:allowed"])
      }
    );

    expect(normalized.surface).toBe("reading");
    expect(normalized.activeTask).toBeNull();
    expect(normalized.context.readingReferenceKey).toBeNull();
  });

  it("migrates version 4 without retaining pins or picker state", () => {
    const keys = learnerWorkspaceStorageKeys("student-1", "course-1", "unit-1");
    if (!keys) throw new Error("expected storage keys");
    const localStorage = new Map<string, string>();
    const sessionStorage = new Map<string, string>();
    localStorage.set(
      keys.persistent,
      JSON.stringify({
        version: 4,
        openedModuleIds: ["module-open"],
        preferences: { navigationVisible: false, fontSize: "large" },
        context: {
          manualReferences: [
            { key: "material:pinned", kind: "material", id: "pinned", moduleId: "module-open" }
          ]
        }
      })
    );
    sessionStorage.set(
      keys.tab,
      JSON.stringify({
        version: 4,
        context: {
          pickerOpen: true,
          expandedModuleIds: ["module-open"],
          expandedReferenceKeys: ["material:pinned"],
          expandedModuleMaterialKeys: { "module-open": ["material:allowed"] },
          readingReferenceKey: "material:allowed",
          bookScrollTop: 80
        }
      })
    );

    const restored = readLearnerWorkspaceState({
      localStorage,
      sessionStorage,
      learnerSub: "student-1",
      courseId: "course-1",
      unitId: "unit-1",
      openableModuleIds: new Set(["module-open"]),
      accessibleReferenceKeys: new Set(["material:allowed"])
    });

    expect(restored.openedModuleIds).toEqual(["module-open"]);
    expect(restored.preferences).toEqual({ navigationVisible: false, fontSize: "large" });
    expect(restored.context.expandedModuleMaterialKeys).toEqual({ "module-open": ["material:allowed"] });
    expect(restored.context.expandedContextModuleIds).toEqual([]);
    expect(restored.context.expandedSubmissionKeys).toEqual([]);
    expect(restored.context.readingReferenceKey).toBe("material:allowed");
    expect(restored.context).not.toHaveProperty("manualReferences");
    expect(restored.context).not.toHaveProperty("pickerOpen");
  });

  it("does not read another learner's or the old unscoped workspace key", () => {
    const localStorage = new Map<string, string>();
    localStorage.set(
      "gustav.learning.unit-workspace:course-1:unit-1",
      JSON.stringify({ version: 5, openedModuleIds: ["module-open"] })
    );

    const restored = readLearnerWorkspaceState({
      localStorage,
      sessionStorage: new Map(),
      learnerSub: "student-1",
      courseId: "course-1",
      unitId: "unit-1",
      openableModuleIds: new Set(["module-open"])
    });

    expect(restored).toEqual(defaultLearnerWorkspaceState());
  });
});
