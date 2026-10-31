import { describe, expect, it } from "vitest";

import { highlightedLearnerGraphModuleIds, learnerGraphNodeIsSelected, learnerGraphFocusId } from "./graph-selection";

describe("learnerGraphFocusId", () => {
  const phase = { id: "empty-phase", type: "phaseBand", data: {} };
  const locked = { id: "locked", type: "unitNode", data: { status: "locked" as const } };
  const open = { id: "open", type: "unitNode", data: { status: "open" as const } };
  const selected = { ...open, id: "selected", selected: true };

  it("prefers a selected module on every screen", () => {
    for (const compact of [true, false]) {
      expect(learnerGraphFocusId([phase, locked, open, selected], compact)).toBe("selected");
    }
  });

  it("starts at the first open module on narrow screens, skipping empty phases", () => {
    expect(learnerGraphFocusId([phase, locked, open, { ...open, id: "later" }], true)).toBe("open");
  });

  it("keeps graph order when no module is open", () => {
    const done = { ...locked, id: "done", data: { status: "done" as const } };
    expect(learnerGraphFocusId([phase, locked, done], true)).toBe("locked");
    expect(learnerGraphFocusId([phase, done, locked], true)).toBe("done");
  });

  it("uses the first phase on desktop or when there are no modules", () => {
    expect(learnerGraphFocusId([phase, locked, open], false)).toBe(phase.id);
    expect(learnerGraphFocusId([phase], true)).toBe(phase.id);
    expect(learnerGraphFocusId([], true)).toBeNull();
  });
});

describe("highlightedLearnerGraphModuleIds", () => {
  it("keeps all open modules highlighted", () => {
    expect(highlightedLearnerGraphModuleIds(["module-2", "module-4"])).toEqual(["module-2", "module-4"]);
  });

  it("deduplicates repeated open tabs", () => {
    expect(highlightedLearnerGraphModuleIds(["module-3", "module-3", "module-5"])).toEqual(["module-3", "module-5"]);
  });

  it("returns an empty list when no module is open", () => {
    expect(highlightedLearnerGraphModuleIds([])).toEqual([]);
  });
});

describe("learnerGraphNodeIsSelected", () => {
  it("marks open unfinished modules as selected", () => {
    expect(learnerGraphNodeIsSelected("open", new Set(["module-1", "module-2"]), "module-2")).toBe(true);
  });

  it("keeps finished modules green even when they are open", () => {
    expect(learnerGraphNodeIsSelected("done", new Set(["module-3"]), "module-3")).toBe(false);
  });

  it("does not mark unopened modules as selected", () => {
    expect(learnerGraphNodeIsSelected("open", new Set(["module-1"]), "module-4")).toBe(false);
  });
});
