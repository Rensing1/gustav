import type { Point } from "./module-graph-layout";

/** Round the supplied orthogonal route without asking another router to move it. */
export function routedEdgePath(input: Point[]): [string, number, number] {
  const points = input.filter((p, i) => i === 0 || p.x !== input[i - 1].x || p.y !== input[i - 1].y);
  if (points.length < 2) return ["", points[0]?.x ?? 0, points[0]?.y ?? 0];
  let path = `M ${points[0].x} ${points[0].y}`;
  const lengths = points.slice(1).map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y));
  // A raw bend is not on its rounded replacement. The longest segment's
  // midpoint stays on the painted path and gives the action room to breathe.
  const labelSegment = lengths.indexOf(Math.max(...lengths));
  const label = { x: (points[labelSegment].x + points[labelSegment + 1].x) / 2,
    y: (points[labelSegment].y + points[labelSegment + 1].y) / 2 };
  for (let i = 1; i < points.length; i++) {
    const previous = points[i - 1], point = points[i], next = points[i + 1];
    if (!next) { path += ` L ${point.x} ${point.y}`; continue; }
    const radius = Math.min(8, lengths[i - 1] / 2, lengths[i] / 2);
    const before = { x: point.x + (previous.x - point.x) * radius / lengths[i - 1], y: point.y + (previous.y - point.y) * radius / lengths[i - 1] };
    const after = { x: point.x + (next.x - point.x) * radius / lengths[i], y: point.y + (next.y - point.y) * radius / lengths[i] };
    path += ` L ${before.x} ${before.y} Q ${point.x} ${point.y} ${after.x} ${after.y}`;
  }
  return [path, label.x, label.y];
}
