import { MODULE_WIDTH, MODULE_HEIGHT, type Point } from "./module-graph-layout";

/**
 * Interpret a drop as one insertion into stored order, not a sort of geometry.
 * Callers must supply the pre-drag positions in the same phase coordinate space.
 * Dependency and authorization checks remain the server's responsibility.
 */
export function reorderedModuleIds(current: string[], movedId: string, drop: Point, before: { id: string; position: Point }[]): string[] {
  const original = before.find((node) => node.id === movedId);
  if (!original || !current.includes(movedId) || Math.hypot(drop.x - original.position.x, drop.y - original.position.y) < 12) return [...current];
  const center = { x: drop.x + MODULE_WIDTH / 2, y: drop.y + MODULE_HEIGHT / 2 };
  const distance = (node: { position: Point }) => Math.hypot(center.x - node.position.x - MODULE_WIDTH / 2, center.y - node.position.y - MODULE_HEIGHT / 2);
  const target = before.filter((node) => node.id !== movedId && current.includes(node.id))
    .sort((a, b) => distance(a) - distance(b) || current.indexOf(a.id) - current.indexOf(b.id))[0];
  if (!target) return [...current];
  const next = current.filter((id) => id !== movedId);
  const afterTarget = center.x >= target.position.x + MODULE_WIDTH / 2;
  next.splice(next.indexOf(target.id) + Number(afterTarget), 0, movedId);
  return next;
}
