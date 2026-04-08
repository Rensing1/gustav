import { describe, expect, it } from "vitest";

import { reopenMaterialEntries, type LearningContentItem, type PaneStackEntry } from "./workspace";

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
});
