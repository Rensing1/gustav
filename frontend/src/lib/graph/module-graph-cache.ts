import { layoutModularGraph, type ModularGeometry } from "./module-graph-layout";

export type ModularGeometryCache = typeof layoutModularGraph;

/** Keep one structure per mounted workspace, never role-specific UI state. */
export function createModularGeometryCache(compute = layoutModularGraph): ModularGeometryCache {
  let lastKey: string | undefined;
  let lastResult: Promise<ModularGeometry> | undefined;
  return (phases, edges, layout) => {
    const key = JSON.stringify({
      phases: phases.map((phase) => ({
        id: phase.id, position: phase.position,
        modules: phase.modules.map(({ id, position_in_phase }) => ({ id, position_in_phase }))
          .sort((a, b) => a.position_in_phase - b.position_in_phase || a.id.localeCompare(b.id))
      })).sort((a, b) => a.position - b.position || a.id.localeCompare(b.id)),
      edges: edges.map(({ from, to }) => ({ from, to })).sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to))
    });
    if (key === lastKey && lastResult) return lastResult;
    lastKey = key;
    const pending = compute(phases, edges, layout);
    lastResult = pending;
    void pending.catch(() => {
      if (lastResult === pending) { lastKey = undefined; lastResult = undefined; }
    });
    return pending;
  };
}
