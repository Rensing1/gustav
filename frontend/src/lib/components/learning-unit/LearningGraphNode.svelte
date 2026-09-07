<script lang="ts">
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";

  import type { LearningFlowNodeData } from "$lib/graph/learning-unit-flow";

  let { data, selected = false }: NodeProps & { data: LearningFlowNodeData; selected?: boolean } = $props();

  function handleClick(event: MouseEvent) {
    event.stopPropagation();
    data.onSelect?.();
  }
</script>

<div class="learning-flow-unit-node-shell">
  <button
    class:teacher-flow-unit-node--compact={data.compact}
    class:teacher-flow-unit-node--selected={selected}
    class:teacher-flow-unit-node--interactive={Boolean(data.openable)}
    class={`teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-${data.status ?? "locked"}`}
    type="button"
    disabled={!data.openable}
    onclick={handleClick}
  >
    <!-- Handles share the bordered card's coordinate space, but are decorative for learners. -->
    {#each [Position.Top, Position.Right, Position.Bottom, Position.Left] as position}
      {#each ["target", "source"] as const as handleType}
        <Handle
          class={`teacher-flow-unit-node__handle teacher-flow-unit-node__handle--${position}-${handleType}`}
          id={`${position}-${handleType}`}
          {position}
          type={handleType}
          isConnectable={false}
          aria-hidden="true"
          role="presentation"
          tabindex={undefined}
        />
      {/each}
    {/each}

    <div class="teacher-flow-unit-node__copy">
      <div class="teacher-flow-unit-node__header">
        <div class="teacher-flow-unit-node__header-main">
          <span>{data.kicker}</span>
        </div>
      </div>

      <strong>{data.title}</strong>

      <div class="teacher-flow-unit-node__meta">
        <small>{data.progressLabel}</small>
        <small>{data.materialsLabel}</small>
      </div>
    </div>
  </button>
</div>
