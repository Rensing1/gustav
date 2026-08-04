import { describe, expect, it } from "vitest";

import {
  learnerNavigationHref,
  resolveLearnerNavigation,
  type LearnerNavigationTarget
} from "./learner-navigation";

describe("learner navigation", () => {
  const access = {
    unitType: "modular" as const,
    openableModuleIds: new Set(["module-a", "module-b"]),
    taskModuleIds: new Map([
      ["task-a", "module-a"],
      ["task-b", "module-b"]
    ])
  };

  it("derives graph, reading, task and result from canonical query parameters", () => {
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit"), access)).toEqual({
      surface: "graph",
      moduleId: null,
      taskId: null,
      panel: null,
      needsNormalization: false
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?module=module-a"), access)).toMatchObject({
      surface: "reading",
      moduleId: "module-a",
      taskId: null
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?module=module-a&task=task-a"), access)).toMatchObject({
      surface: "task",
      moduleId: "module-a",
      taskId: "task-a",
      panel: null
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?module=module-a&task=task-a&panel=result"), access)).toMatchObject({
      surface: "task",
      panel: "result"
    });
  });

  it("normalizes legacy view and history links to the nearest canonical state", () => {
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?view=overview"), access)).toMatchObject({
      surface: "graph",
      needsNormalization: true
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?view=content&module=module-a"), access)).toMatchObject({
      surface: "reading",
      moduleId: "module-a",
      needsNormalization: true
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?module=module-a&history=task-a"), access)).toMatchObject({
      surface: "task",
      taskId: "task-a",
      panel: "result",
      needsNormalization: true
    });
  });

  it("rejects inaccessible or mismatched module and task combinations", () => {
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?module=locked"), access)).toMatchObject({
      surface: "graph",
      moduleId: null,
      needsNormalization: true
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?module=module-b&task=task-a"), access)).toMatchObject({
      surface: "reading",
      moduleId: "module-b",
      taskId: null,
      needsNormalization: true
    });
  });

  it("keeps linear units out of an artificial graph state", () => {
    const linear = {
      unitType: "linear" as const,
      openableModuleIds: new Set<string>(),
      taskModuleIds: new Map([["task-a", null]])
    };
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit"), linear)).toMatchObject({
      surface: "reading",
      moduleId: null
    });
    expect(resolveLearnerNavigation(new URL("https://app.localhost/unit?task=task-a"), linear)).toMatchObject({
      surface: "task",
      taskId: "task-a"
    });
  });

  it("builds canonical hrefs and removes obsolete state parameters", () => {
    const base = new URL("https://app.localhost/unit?view=content&history=task-a&message=submitted");
    const targets: Array<[LearnerNavigationTarget, string]> = [
      [{ surface: "graph", moduleId: null, taskId: null, panel: null }, "/unit"],
      [{ surface: "reading", moduleId: "module-a", taskId: null, panel: null }, "/unit?module=module-a"],
      [{ surface: "task", moduleId: "module-a", taskId: "task-a", panel: null }, "/unit?module=module-a&task=task-a"],
      [{ surface: "task", moduleId: "module-a", taskId: "task-a", panel: "result" }, "/unit?module=module-a&task=task-a&panel=result"]
    ];

    for (const [target, expected] of targets) {
      expect(learnerNavigationHref(base, target)).toBe(expected);
    }
  });
});
