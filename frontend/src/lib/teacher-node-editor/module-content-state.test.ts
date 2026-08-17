import { describe, expect, it } from "vitest";

import {
  contentSelectionParam,
  draftStorageKey,
  formatPrerequisiteSummary,
  hasMeaningfulDraftChanges,
  parseContentSelection
} from "./module-content-state";

const content = {
  materials: [{ id: "material-1" }, { id: "material-2" }],
  tasks: [{ id: "task-1" }]
};

describe("module content state", () => {
  it("starts in the overview without a content parameter", () => {
    expect(parseContentSelection(null, content)).toEqual({ kind: "overview" });
  });

  it("resolves valid material and task selections", () => {
    expect(parseContentSelection("material:material-2", content)).toEqual({
      kind: "material",
      id: "material-2"
    });
    expect(parseContentSelection("task:task-1", content)).toEqual({ kind: "task", id: "task-1" });
  });

  it("falls back safely for malformed or inaccessible selections", () => {
    expect(parseContentSelection("material:foreign", content)).toEqual({ kind: "overview" });
    expect(parseContentSelection("task:", content)).toEqual({ kind: "overview" });
    expect(parseContentSelection("unknown:task-1", content)).toEqual({ kind: "overview" });
  });

  it("serializes only persisted content selections", () => {
    expect(contentSelectionParam({ kind: "material", id: "material-1" })).toBe("material:material-1");
    expect(contentSelectionParam({ kind: "task", id: "task-1" })).toBe("task:task-1");
    expect(contentSelectionParam({ kind: "overview" })).toBeNull();
    expect(contentSelectionParam({ kind: "new-material" })).toBeNull();
  });

  it("scopes drafts by teacher, unit, module and target", () => {
    const first = draftStorageKey({
      teacherSub: "teacher-1",
      unitId: "unit-1",
      nodeId: "module-1",
      target: "task:task-1"
    });
    const secondTeacher = draftStorageKey({
      teacherSub: "teacher-2",
      unitId: "unit-1",
      nodeId: "module-1",
      target: "task:task-1"
    });

    expect(first).toContain("teacher-1");
    expect(first).toContain("unit-1");
    expect(first).toContain("module-1");
    expect(first).toContain("task%3Atask-1");
    expect(secondTeacher).not.toBe(first);
  });

  it("formats the module prerequisite rule in plain language", () => {
    expect(formatPrerequisiteSummary(0, 0)).toBe("Keine Voraussetzungen");
    expect(formatPrerequisiteSummary(1, 2)).toBe("Freigabe nach 1 von 2 Voraussetzungen");
    expect(formatPrerequisiteSummary(2, 3)).toBe("Freigabe nach 2 von 3 Voraussetzungen");
  });

  it("distinguishes unchanged, changed and fully reverted form snapshots", () => {
    const baseline = {
      kind: "markdown",
      title: "Merkblatt",
      body_md: "Gespeicherter Inhalt",
      alt_text: ""
    };

    expect(hasMeaningfulDraftChanges({ ...baseline }, baseline)).toBe(false);
    expect(hasMeaningfulDraftChanges({ ...baseline, title: "Merkblatt überarbeitet" }, baseline)).toBe(true);
    expect(hasMeaningfulDraftChanges({ ...baseline, title: "Merkblatt" }, baseline)).toBe(false);
    expect(hasMeaningfulDraftChanges({ kind: "markdown", title: "Merkblatt", body_md: "Gespeicherter Inhalt" }, baseline)).toBe(false);
  });
});
