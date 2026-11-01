import { describe, expect, it, vi } from "vitest";
import { createModularGeometryCache } from "./module-graph-cache";
import { routedEdgePath } from "./routed-edge-path";
import { reorderedModuleIds } from "./module-reorder";

describe("modular geometry lifecycle", () => {
  const phases = [{ id: "p", position: 1, modules: [{ id: "a", position_in_phase: 1 }] }];
  it("reuses only the last structure and retries failed calculations", async () => {
    const compute = vi.fn().mockResolvedValue({ phases: [], modules: new Map(), edges: new Map(), railWidth: 72 });
    const get = createModularGeometryCache(compute);
    const engine = vi.fn();
    const first = await get(phases, [], engine);
    expect(await get(structuredClone(phases), [], engine)).toBe(first);
    expect(compute).toHaveBeenCalledTimes(1);
    compute.mockRejectedValueOnce(Error("failed"));
    const changed = [{ ...phases[0], position: 2 }];
    await expect(get(changed, [], engine)).rejects.toThrow("failed");
    await get(changed, [], engine);
    expect(compute).toHaveBeenCalledTimes(3);
  });

  it("does not let an old rejection evict a newer successful geometry", async () => {
    let rejectOld!: (error: Error) => void;
    const newer = { phases: [], modules: new Map(), edges: new Map(), railWidth: 72 };
    const compute = vi.fn().mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; })).mockResolvedValue(newer);
    const get = createModularGeometryCache(compute);
    const engine = vi.fn();
    const old = get(phases, [], engine);
    const rejection = expect(old).rejects.toThrow("old");
    const changed = [{ ...phases[0], position: 2 }];
    expect(await get(changed, [], engine)).toBe(newer);
    rejectOld(Error("old"));
    await rejection;
    expect(await get(changed, [], engine)).toBe(newer);
    expect(compute).toHaveBeenCalledTimes(2);
  });
});

describe("calculated edge rendering", () => {
  it("keeps routed endpoints and places the action on the actual path", () => {
    const [path, x, y] = routedEdgePath([{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }]);
    expect(path).toMatch(/^M 0 0/);
    expect(path).toMatch(/Q/);
    expect(path).toMatch(/100 100$/);
    // The raw bend itself is not on a rounded corner. Use a straight segment.
    expect([x, y]).toEqual([50, 0]);
  });
  it("handles duplicate points and short segments without invalid arcs", () => {
    const [path] = routedEdgePath([{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }]);
    expect(path).not.toMatch(/NaN|Infinity/);
    expect(path).toMatch(/1 1$/);
  });
});

describe("moving one module without sorting the whole visual graph", () => {
  const positions = [
    { id: "a", position: { x: 0, y: 100 } },
    { id: "b", position: { x: 300, y: 0 } },
    { id: "c", position: { x: 300, y: 200 } },
    { id: "d", position: { x: 600, y: 100 } }
  ];
  it("does not reorder a branch after an unchanged or tiny drag", () => {
    expect(reorderedModuleIds(["a", "b", "c", "d"], "b", { x: 302, y: 1 }, positions))
      .toEqual(["a", "b", "c", "d"]);
  });
  it("moves only the dragged ID relative to the nearest target card", () => {
    expect(reorderedModuleIds(["a", "b", "c", "d"], "a", { x: 550, y: 100 }, positions))
      .toEqual(["b", "c", "a", "d"]);
    expect(reorderedModuleIds(["a", "b", "c", "d"], "a", { x: 800, y: 100 }, positions))
      .toEqual(["b", "c", "d", "a"]);
  });
});
