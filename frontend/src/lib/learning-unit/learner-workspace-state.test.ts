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
  it("uses version 3 for the book, work and deliberate reader positions", () => {
    expect(LEARNER_WORKSPACE_STORAGE_VERSION).toBe(3);
    expect(defaultLearnerWorkspaceState().context).toMatchObject({
      bookScrollTop: 0,
      workScrollTop: 0,
      readerScrollTop: 0
    });
  });

  it("starts in the reading surface without a second work surface", () => {
    expect(defaultLearnerWorkspaceState()).toMatchObject({
      surface: "reading",
      activeTask: null,
      openedModuleIds: [],
      collapsedItemKeys: [],
      context: {
        compactSurface: "task",
        manualReferences: [],
        pickerOpen: false,
        readingReferenceKey: null
      },
      preferences: {
        navigationVisible: true,
        fontSize: "standard"
      }
    });
  });

  it("uses learner, course and unit in both storage keys", () => {
    expect(learnerWorkspaceStorageKeys("student/sub", "course-1", "unit-1")).toEqual({
      persistent: "gustav.learning.workspace:student%2Fsub:course-1:unit-1",
      tab: "gustav.learning.workspace:student%2Fsub:course-1:unit-1:tab"
    });
    expect(learnerWorkspaceStorageKeys(null, "course-1", "unit-1")).toBeNull();
  });

  it("does not read the old unscoped workspace key", () => {
    const localStorage = new Map<string, string>();
    localStorage.set(
      "gustav.learning.unit-workspace:course-1:unit-1",
      JSON.stringify({ view: "content", splitView: true, openTabs: ["module-open"] })
    );

    const restored = readLearnerWorkspaceState({
      localStorage,
      sessionStorage: new Map(),
      learnerSub: "student-1",
      courseId: "course-1",
      unitId: "unit-1",
      openableModuleIds: new Set(["module-open"]),
      accessibleReferenceKeys: new Set()
    });

    expect(restored).toEqual(defaultLearnerWorkspaceState());
  });

  it("keeps persistent pins and tab-local reading state separate", () => {
    const state: LearnerWorkspaceState = {
      ...defaultLearnerWorkspaceState(),
      surface: "task",
      openedModuleIds: ["module-a"],
      activeTask: {
        itemKey: "task:task-a",
        taskId: "task-a",
        moduleId: "module-a",
        status: "editing",
        editorMode: "text"
      },
      context: {
        compactSurface: "materials",
        manualReferences: [
          { key: "material:material-a", kind: "material", id: "material-a", moduleId: "module-a", taskId: null }
        ],
        expandedReferenceKeys: ["material:material-a"],
        pickerOpen: false,
        expandedModuleIds: [],
        readingReferenceKey: "material:material-a",
        bookScrollTop: 420,
        workScrollTop: 180,
        readerScrollTop: 75
      },
      returnPosition: { moduleId: "module-a", scrollY: 640, focusId: "task-row-task-a" }
    };

    const persistent = JSON.parse(serializeLearnerWorkspacePersistentState(state));
    const tab = JSON.parse(serializeLearnerWorkspaceTabState(state));

    expect(persistent.context.manualReferences).toHaveLength(1);
    expect(persistent.preferences.fontSize).toBe("standard");
    expect(persistent).not.toHaveProperty("activeTask");
    expect(persistent).not.toHaveProperty("readingReferenceKey");
    expect(tab.activeTask.taskId).toBe("task-a");
    expect(tab.context.readingReferenceKey).toBe("material:material-a");
    expect(tab.context.bookScrollTop).toBe(420);
    expect(tab.context.workScrollTop).toBe(180);
    expect(tab.context.readerScrollTop).toBe(75);
    expect(tab).not.toHaveProperty("manualReferences");
  });

  it("drops locked modules, inaccessible references and an invalid active task", () => {
    const normalized = normalizeLearnerWorkspaceState(
      {
        ...defaultLearnerWorkspaceState(),
        surface: "task",
        openedModuleIds: ["module-locked", "module-open"],
        activeTask: {
          itemKey: "task:locked-task",
          taskId: "locked-task",
          moduleId: "module-locked",
          status: "editing",
          editorMode: "upload"
        },
        context: {
          compactSurface: "materials",
          manualReferences: [
            { key: "material:allowed", kind: "material", id: "allowed", moduleId: "module-open", taskId: null },
            { key: "material:locked", kind: "material", id: "locked", moduleId: "module-locked", taskId: null }
          ],
          expandedReferenceKeys: ["material:allowed", "material:locked"],
          pickerOpen: false,
          expandedModuleIds: ["module-open", "module-locked"],
          readingReferenceKey: "material:locked",
          bookScrollTop: 100,
          workScrollTop: 50,
          readerScrollTop: 25
        }
      },
      {
        openableModuleIds: new Set(["module-open"]),
        accessibleTaskKeys: new Set(["task:other"]),
        accessibleReferenceKeys: new Set(["material:allowed"])
      }
    );

    expect(normalized.surface).toBe("reading");
    expect(normalized.openedModuleIds).toEqual(["module-open"]);
    expect(normalized.activeTask).toBeNull();
    expect(normalized.context.manualReferences.map((entry) => entry.key)).toEqual(["material:allowed"]);
    expect(normalized.context.expandedReferenceKeys).toEqual(["material:allowed"]);
    expect(normalized.context.readingReferenceKey).toBeNull();
  });

  it("restores persistent state only from local storage and reading state only from the current tab", () => {
    const keys = learnerWorkspaceStorageKeys("student-1", "course-1", "unit-1");
    if (!keys) throw new Error("expected storage keys");
    const localStorage = new Map<string, string>();
    const sessionStorage = new Map<string, string>();
    localStorage.set(
      keys.persistent,
      JSON.stringify({
        version: 1,
        openedModuleIds: ["module-open"],
        preferences: { navigationVisible: false, fontSize: "large" },
        context: {
          manualReferences: [
            { key: "material:allowed", kind: "material", id: "allowed", moduleId: "module-open", taskId: null }
          ]
        }
      })
    );
    sessionStorage.set(
      keys.tab,
      JSON.stringify({
        version: 1,
        surface: "task",
        activeTask: {
          itemKey: "task:task-open",
          taskId: "task-open",
          moduleId: "module-open",
          status: "result",
          editorMode: null
        },
        context: {
          compactSurface: "materials",
          expandedReferenceKeys: ["material:allowed"],
          pickerOpen: true,
          expandedModuleIds: ["module-open"],
          readingReferenceKey: "material:allowed",
          bookScrollTop: 80,
          workScrollTop: 40,
          readerScrollTop: 20
        },
        returnPosition: { moduleId: "module-open", scrollY: 300, focusId: "task-row-task-open" }
      })
    );

    const restored = readLearnerWorkspaceState({
      localStorage,
      sessionStorage,
      learnerSub: "student-1",
      courseId: "course-1",
      unitId: "unit-1",
      openableModuleIds: new Set(["module-open"]),
      accessibleTaskKeys: new Set(["task:task-open"]),
      accessibleReferenceKeys: new Set(["material:allowed"])
    });

    expect(restored.surface).toBe("task");
    expect(restored.activeTask?.status).toBe("result");
    expect(restored.openedModuleIds).toEqual(["module-open"]);
    expect(restored.preferences).toEqual({ navigationVisible: false, fontSize: "large" });
    expect(restored.context.readingReferenceKey).toBe("material:allowed");
    expect(restored.context.bookScrollTop).toBe(80);
    expect(restored.context.workScrollTop).toBe(40);
    expect(restored.context.readerScrollTop).toBe(20);
  });

  it("migrates version 2 without reopening its automatically focused reader", () => {
    const keys = learnerWorkspaceStorageKeys("student-1", "course-1", "unit-1");
    if (!keys) throw new Error("expected storage keys");
    const sessionStorage = new Map<string, string>();
    sessionStorage.set(
      keys.tab,
      JSON.stringify({
        version: 2,
        context: {
          expandedReferenceKeys: ["material:allowed"],
          readingReferenceKey: "material:allowed",
          scrollTop: 96
        }
      })
    );

    const restored = readLearnerWorkspaceState({
      localStorage: new Map(),
      sessionStorage,
      learnerSub: "student-1",
      courseId: "course-1",
      unitId: "unit-1",
      openableModuleIds: new Set(["module-open"]),
      accessibleReferenceKeys: new Set(["material:allowed"])
    });

    expect(restored.context.expandedReferenceKeys).toEqual(["material:allowed"]);
    expect(restored.context.readingReferenceKey).toBeNull();
    expect(restored.context.bookScrollTop).toBe(96);
  });

  it("keeps references from accessible modules before their content is loaded", () => {
    const normalized = normalizeLearnerWorkspaceState(
      {
        context: {
          manualReferences: [
            {
              key: "material:later",
              kind: "material",
              id: "later",
              moduleId: "module-open",
              taskId: null
            },
            {
              key: "material:locked",
              kind: "material",
              id: "locked",
              moduleId: "module-locked",
              taskId: null
            }
          ]
        }
      },
      {
        openableModuleIds: new Set(["module-open"])
      }
    );

    expect(normalized.context.manualReferences.map((entry) => entry.key)).toEqual(["material:later"]);
  });
});
