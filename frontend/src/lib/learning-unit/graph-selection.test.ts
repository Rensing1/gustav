import { describe, expect, it } from "vitest";

import { highlightedLearnerGraphModuleIds, learnerGraphNodeIsSelected } from "./graph-selection";

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
