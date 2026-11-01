import ELK from "elkjs/lib/elk.bundled.js";
import { describe, expect, it } from "vitest";
import { layoutModularGraph, MODULE_WIDTH, MODULE_HEIGHT } from "./module-graph-layout";

const elk = new ELK();
const layout = elk.layout.bind(elk);
function phase(id: string, ids: string[], position = 1) {
  return { id, position, modules: ids.map((id, index) => ({ id, position_in_phase: index + 1 })) };
}
function chain(ids: string[]) { return ids.slice(1).map((to, i) => ({ from: ids[i], to })); }

/** Orthogonal segments may touch their own endpoint border, never a card interior. */
function expectClearPaths(result: Awaited<ReturnType<typeof layoutModularGraph>>) {
  for (const [key, route] of result.edges) {
    expect(route.points.length, key).toBeGreaterThanOrEqual(2);
    for (let i = 1; i < route.points.length; i++) {
      const a = route.points[i - 1], b = route.points[i];
      expect(Math.abs(a.x - b.x) < 0.01 || Math.abs(a.y - b.y) < 0.01, `${key} is orthogonal`).toBe(true);
      for (const node of result.modules.values()) {
        const parent = result.phases.find((p) => p.id === node.phaseId)!;
        const x = parent.x + node.x, y = parent.y + node.y;
        const intersects = Math.abs(a.x - b.x) < 0.01
          ? a.x > x + 0.01 && a.x < x + MODULE_WIDTH - 0.01 && Math.max(a.y, b.y) > y + 0.01 && Math.min(a.y, b.y) < y + MODULE_HEIGHT - 0.01
          : a.y > y + 0.01 && a.y < y + MODULE_HEIGHT - 0.01 && Math.max(a.x, b.x) > x + 0.01 && Math.min(a.x, b.x) < x + MODULE_WIDTH - 0.01;
        expect(intersects, `${key} crosses ${node.id}`).toBe(false);
      }
      // Header height is reserved regardless of the actual title length.
      for (const parent of result.phases) {
        const crossesHeader = Math.abs(a.x - b.x) < 0.01
          ? a.x > parent.x + result.railWidth && a.x < parent.x + parent.width - result.railWidth
            && Math.max(a.y, b.y) > parent.y && Math.min(a.y, b.y) < parent.y + 90
          : a.y > parent.y && a.y < parent.y + 90
            && Math.max(a.x, b.x) > parent.x + result.railWidth && Math.min(a.x, b.x) < parent.x + parent.width - result.railWidth;
        expect(crossesHeader, `${key} crosses header ${parent.id}`).toBe(false);
      }
    }
  }
}

describe("module graph geometry with real ELK", () => {
  it.each([1, 3, 4, 5, 8])("places %i chained modules in horizontal four-column rows", async (count) => {
    const ids = Array.from({ length: count }, (_, i) => `m${i}`);
    const result = await layoutModularGraph([phase("p", ids)], chain(ids), layout);
    for (let i = 0; i < count; i++) {
      const node = result.modules.get(ids[i])!;
      expect(node.rowIndex).toBe(Math.floor(i / 4));
      if (i % 4) {
        const previous = result.modules.get(ids[i - 1])!;
        expect(node.x).toBeGreaterThan(previous.x);
        expect(node.y).toBeCloseTo(previous.y);
      }
    }
    expect(result.edges.size).toBe(Math.max(0, count - 1));
    if (count > 4) expect(result.modules.get(ids[4])!.x).toBeCloseTo(result.modules.get(ids[0])!.x);
    expectClearPaths(result);
  });

  it("routes branches, row returns and cross-phase edges around all cards and headers", async () => {
    const first = ["a", "b", "c", "d", "e", "f", "g", "h"];
    const second = ["i", "j", "k", "l", "m"];
    const phases = [phase("p1", first), phase("p2", second, 2), phase("empty", [], 3)];
    const edges = [...chain(first), { from: "d", to: "f" }, ...chain(second),
      { from: "b", to: "j" }, { from: "e", to: "m" }, { from: "h", to: "i" }];
    const result = await layoutModularGraph(phases, edges, layout);
    expect(result.modules.size).toBe(13);
    expect(result.edges.size).toBe(edges.length);
    expect(new Set(result.phases.map((p) => p.width)).size).toBe(1);
    expectClearPaths(result);
    const shuffled = await layoutModularGraph([...phases].reverse().map((p) => ({ ...p, modules: [...p.modules].reverse() })), [...edges].reverse(), layout);
    expect(shuffled).toEqual(result);
  });

  it("keeps unrelated modules in a grid and retains empty phases without virtual nodes", async () => {
    const result = await layoutModularGraph([phase("p", ["a", "b", "c", "d", "e"]), phase("empty", [], 2)], [], layout);
    expect(result.modules.size).toBe(5);
    expect(result.edges.size).toBe(0);
    expect(result.phases).toHaveLength(2);
    expect(result.modules.get("e")!.y).toBeGreaterThan(result.modules.get("a")!.y);
    expect(result.modules.get("e")!.x).toBeCloseTo(result.modules.get("a")!.x);
  });

  it("keeps a wide branch intact and routes its skipping edge outside intermediate cards", async () => {
    const ids = ["a", "b", "c", "d", "e", "f", "g", "h"];
    const edges = [...chain(ids), { from: "a", to: "f" }];
    const result = await layoutModularGraph([phase("p", ids)], edges, layout);
    expect(result.modules.get("f")!.rowIndex).toBe(0);
    expect(result.modules.get("g")!.rowIndex).toBe(1);
    expectClearPaths(result);
  });

  it("preserves multiple starting modules, a nested join and phase-crossing exits", async () => {
    const ids = ["a", "b", "c", "d", "e", "f", "g"];
    const edges = [{ from: "a", to: "c" }, { from: "b", to: "c" },
      { from: "c", to: "d" }, { from: "c", to: "e" }, { from: "d", to: "f" },
      { from: "e", to: "f" }, { from: "f", to: "g" }, { from: "b", to: "next" }, { from: "g", to: "next" }];
    const result = await layoutModularGraph([phase("p", ids), phase("q", ["next"], 2)], edges, layout);
    expect(result.modules.get("a")!.x).toBeCloseTo(result.modules.get("b")!.x);
    expect(result.modules.get("c")!.x).toBeGreaterThan(result.modules.get("a")!.x);
    expectClearPaths(result);
  });

  it("propagates engine errors without fabricating fallback positions", async () => {
    await expect(layoutModularGraph([phase("p", ["a", "b"])], chain(["a", "b"]), async () => { throw Error("engine failed"); }))
      .rejects.toThrow("engine failed");
  });
});
