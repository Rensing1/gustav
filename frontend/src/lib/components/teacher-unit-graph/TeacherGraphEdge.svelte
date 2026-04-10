<script lang="ts">
  import { enhance } from "$app/forms";
  import {
    BaseEdge,
    getSmoothStepPath,
    type EdgeProps
  } from "@xyflow/svelte";

  import type { TeacherFlowEdgeData, SmoothStepPathOptionsLike } from "$lib/graph/teacher-unit-flow";

  let {
    id,
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

  const edgeGeometry = $derived.by(() =>
    getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      borderRadius: pathOptions?.borderRadius ?? 18,
      offset: pathOptions?.offset ?? 0
    })
  );

  const enhanceGraphForm = () => {
    return async ({ update }: { update: (options?: { reset?: boolean; invalidateAll?: boolean }) => Promise<void> }) => {
      await update({ reset: false, invalidateAll: false });
    };
  };
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
    <form method="POST" action="?/deleteEdge" class="teacher-flow-edge-chip__form" use:enhance={enhanceGraphForm}>
      <input type="hidden" name="from_module_id" value={data.from} />
      <input type="hidden" name="to_module_id" value={data.to} />
      <button class="teacher-flow-edge-chip__button nodrag nopan" type="submit" aria-label="Kante löschen">
        Verbindung lösen
      </button>
    </form>
  </foreignObject>
{/if}
