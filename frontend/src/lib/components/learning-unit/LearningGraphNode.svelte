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
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--top-target"
    id="top-target"
    position={Position.Top}
    type="target"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--top-source"
    id="top-source"
    position={Position.Top}
    type="source"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--right-target"
    id="right-target"
    position={Position.Right}
    type="target"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--right-source"
    id="right-source"
    position={Position.Right}
    type="source"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--bottom-target"
    id="bottom-target"
    position={Position.Bottom}
    type="target"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--bottom-source"
    id="bottom-source"
    position={Position.Bottom}
    type="source"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--left-target"
    id="left-target"
    position={Position.Left}
    type="target"
  />
  <Handle
    class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--left-source"
    id="left-source"
    position={Position.Left}
    type="source"
  />

  <button
    class:teacher-flow-unit-node--selected={selected}
    class:teacher-flow-unit-node--interactive={Boolean(data.openable)}
    class={`teacher-flow-unit-node teacher-flow-unit-node--learner teacher-flow-unit-node--learner-${data.status ?? "locked"}`}
    type="button"
    disabled={!data.openable}
    onclick={handleClick}
  >
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
