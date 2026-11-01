import { describe, expect, it } from "vitest";
import { planPhaseRows } from "./module-graph-rows";

function modules(ids: string[]) {
  return ids.map((id, index) => ({ id, position_in_phase: index + 1 }));
}
function chain(ids: string[]) {
  return ids.slice(1).map((to, index) => ({ from: ids[index], to }));
}

describe("structural module graph rows", () => {
  it.each([1, 3, 4, 5, 8, 13])("wraps a %i-module chain after four columns", (count) => {
    const ids = Array.from({ length: count }, (_, i) => String(i));
    expect(planPhaseRows(modules(ids), chain(ids))).toEqual(
      Array.from({ length: Math.ceil(count / 4) }, (_, row) => ids.slice(row * 4, row * 4 + 4))
    );
  });

  it("cuts before a branch rather than through its open paths", () => {
    const ids = ["a", "b", "c", "d", "e", "f", "g"];
    const edges = [...chain(ids.slice(0, 4)), { from: "d", to: "e" }, { from: "d", to: "f" },
      { from: "e", to: "g" }, { from: "f", to: "g" }];
    expect(planPhaseRows(modules(ids), edges)).toEqual([["a", "b", "c"], ["d", "e", "f", "g"]]);
  });

  it("keeps a wide branching area together, then wraps its tail", () => {
    const ids = ["a", "b", "c", "d", "e", "f", "g", "h"];
    const edges = [...chain(ids), { from: "a", to: "f" }];
    expect(planPhaseRows(modules(ids), edges)).toEqual([["a", "b", "c", "d", "e", "f"], ["g", "h"]]);
  });

  it("counts skipping edges when deciding whether a branch is closed", () => {
    const ids = ["a", "b", "c", "d", "e", "f"];
    expect(planPhaseRows(modules(ids), [...chain(ids), { from: "a", to: "f" }])).toEqual([ids]);
  });

  it("packs free modules into a grid without treating them as a chain", () => {
    const ids = ["a", "b", "c", "d", "e"];
    expect(planPhaseRows(modules(ids), [])).toEqual([["a", "b", "c", "d"], ["e"]]);
  });

  it("orders separate components by their earliest stored position", () => {
    const items = modules(["a", "b", "c", "d", "e"]);
    expect(planPhaseRows(items, [{ from: "a", to: "d" }, { from: "b", to: "e" }]))
      .toEqual([["a", "d"], ["b", "e"], ["c"]]);
  });

  it("is stable for shuffled inputs and ignores edges outside this phase", () => {
    const items = modules(["a", "b", "c", "d", "e"]);
    const edges = [...chain(items.map((m) => m.id)), { from: "e", to: "next-phase" }];
    const before = JSON.stringify({ items, edges });
    expect(planPhaseRows([...items].reverse(), [...edges].reverse())).toEqual([["a", "b", "c", "d"], ["e"]]);
    expect(JSON.stringify({ items, edges })).toBe(before);
  });

  it("handles empty phases and rejects cycles instead of losing modules", () => {
    expect(planPhaseRows([], [])).toEqual([]);
    expect(() => planPhaseRows(modules(["a", "b"]), [{ from: "a", to: "b" }, { from: "b", to: "a" }]))
      .toThrow(/cycle/i);
  });
});
