export type ModuleOrder = { id: string; position_in_phase: number };
export type ModuleEdge = { from: string; to: string };
export type ModulePhase = { id: string; position: number; modules: ModuleOrder[] };

/**
 * Plan readable rows without interpreting order as a prerequisite.
 * The caller supplies authorized graph data; this pure presentation function
 * neither changes stored positions nor makes release/permission decisions.
 * A single crossing edge is a safe cut: all branches before it have closed.
 */
export function planPhaseRows(modules: ModuleOrder[], edges: ModuleEdge[]): string[][] {
  const ordered = [...modules].sort((a, b) => a.position_in_phase - b.position_in_phase || a.id.localeCompare(b.id));
  const ids = new Set(ordered.map((m) => m.id));
  const internal = edges.filter((e) => ids.has(e.from) && ids.has(e.to));
  const neighbors = new Map(ordered.map((m) => [m.id, new Set<string>()]));
  const outgoing = new Map(ordered.map((m) => [m.id, [] as string[]]));
  const indegree = new Map(ordered.map((m) => [m.id, 0]));
  for (const edge of internal) {
    neighbors.get(edge.from)!.add(edge.to);
    neighbors.get(edge.to)!.add(edge.from);
    outgoing.get(edge.from)!.push(edge.to);
    indegree.set(edge.to, indegree.get(edge.to)! + 1);
  }

  const level = new Map(ordered.map((m) => [m.id, 0]));
  const queue = ordered.filter((m) => indegree.get(m.id) === 0).map((m) => m.id);
  for (let head = 0; head < queue.length; head++) {
    for (const next of outgoing.get(queue[head])!) {
      level.set(next, Math.max(level.get(next)!, level.get(queue[head])! + 1));
      indegree.set(next, indegree.get(next)! - 1);
      if (indegree.get(next) === 0) queue.push(next);
    }
  }
  if (queue.length !== ordered.length) throw Error("Module graph contains a cycle");

  const rows: string[][] = [];
  const visited = new Set<string>();
  let free: string[] = [];
  const flushFree = () => {
    for (let i = 0; i < free.length; i += 4) rows.push(free.slice(i, i + 4));
    free = [];
  };
  for (const module of ordered) {
    if (visited.has(module.id)) continue;
    const component = [module.id];
    visited.add(module.id);
    for (let head = 0; head < component.length; head++) {
      for (const next of neighbors.get(component[head])!) {
        if (!visited.has(next)) { visited.add(next); component.push(next); }
      }
    }
    if (component.length === 1) { free.push(module.id); continue; }
    flushFree();
    const members = new Set(component);
    const componentOrder = ordered.filter((m) => members.has(m.id));
    const last = Math.max(...component.map((id) => level.get(id)!)) + 1;
    // Difference counts include long edges at every boundary they cross.
    const crossing = new Array<number>(last + 1).fill(0);
    for (const id of component) {
      for (const next of outgoing.get(id)!) {
        crossing[level.get(id)! + 1]++;
        crossing[level.get(next)! + 1]--;
      }
    }
    const safe: number[] = [];
    let count = 0;
    for (let boundary = 1; boundary < last; boundary++) {
      count += crossing[boundary];
      if (count === 1) safe.push(boundary);
    }
    let start = 0;
    while (start < last) {
      const within = safe.filter((cut) => cut > start && cut <= start + 4);
      const end = last <= start + 4 ? last : within.at(-1) ?? safe.find((cut) => cut > start + 4) ?? last;
      rows.push(componentOrder.filter((m) => level.get(m.id)! >= start && level.get(m.id)! < end).map((m) => m.id));
      start = end;
    }
  }
  flushFree();
  return rows;
}
