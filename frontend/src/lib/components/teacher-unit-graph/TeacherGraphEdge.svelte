<script lang="ts">
  import { untrack } from "svelte";
  import { enhance } from "$app/forms";
  import {
    BaseEdge,
    getSmoothStepPath,
    useInternalNode,
    type EdgeProps
  } from "@xyflow/svelte";

  import type { TeacherFlowEdgeData, SmoothStepPathOptionsLike } from "$lib/graph/teacher-unit-flow";
  import { routedEdgePath } from "$lib/graph/routed-edge-path";

  let {
    id,
    source,
    target,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    selected = false,
    markerEnd,
    data,
    pathOptions
  }: EdgeProps & {
    data?: TeacherFlowEdgeData;
    pathOptions?: SmoothStepPathOptionsLike;
    selected?: boolean;
  } = $props();

  // Edges are keyed by their source/target pair; changing an endpoint creates
  // a new edge component, so these subscriptions intentionally stay fixed.
  const sourceNode = useInternalNode(untrack(() => source));
  const targetNode = useInternalNode(untrack(() => target));
  const dragging = $derived(Boolean(sourceNode.current?.dragging || targetNode.current?.dragging));
  const edgeGeometry = $derived.by(() => {
    const points = data?.routePoints;
    // During dragging, live handles keep the preview attached. On drop the
    // structural layout supplies the complete route again.
    if (points && !dragging) return routedEdgePath([
      // Visible handles extend slightly beyond the card border. Preserve the
      // calculated bends, but terminate at the actual handle boundary.
      { x: sourceX, y: sourceY }, ...points.slice(1, -1), { x: targetX, y: targetY }
    ]);
    return getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      borderRadius: pathOptions?.borderRadius ?? 18,
      offset: pathOptions?.offset ?? 0
    });
  });
</script>

<BaseEdge path={edgeGeometry[0]} {markerEnd} />

{#if selected && data}
  <foreignObject
    x={edgeGeometry[1] - 72}
    y={edgeGeometry[2] - 18}
    width="144"
    height="36"
    class="teacher-flow-edge-chip"
  >
    <form method="POST" action="?/deleteEdge" class="teacher-flow-edge-chip__form" use:enhance={data.enhanceGraphForm}>
      <input type="hidden" name="from_module_id" value={data.from} />
      <input type="hidden" name="to_module_id" value={data.to} />
      <button class="teacher-flow-edge-chip__button nodrag nopan" type="submit" aria-label="Kante löschen">
        Verbindung lösen
      </button>
    </form>
  </foreignObject>
{/if}
