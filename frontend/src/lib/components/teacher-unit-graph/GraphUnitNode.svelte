<script lang="ts">
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";

  import type { TeacherFlowNodeData } from "$lib/graph/teacher-unit-flow";

  let { data, selected = false }: NodeProps & { data: TeacherFlowNodeData; selected?: boolean } = $props();

  function stopPropagation(event: MouseEvent) {
    event.stopPropagation();
  }
</script>

<div class:teacher-flow-unit-node--compact={data.compact} class:teacher-flow-unit-node--selected={selected} class="teacher-flow-unit-node">
  {#if data.connectable}
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
  {/if}

  <div class="teacher-flow-unit-node__copy">
    <div class="teacher-flow-unit-node__header">
      <span>{data.kicker}</span>
      {#if data.editorHref}
        <a class="teacher-flow-unit-node__editor nodrag nopan" href={data.editorHref} onclick={stopPropagation}>
          Öffnen
        </a>
      {/if}
    </div>
    <strong>{data.title}</strong>
    <small>{data.meta}</small>
  </div>

  {#if selected && (data.quickHref || data.editorHref || data.createHref)}
    <div class="teacher-flow-unit-node__popover nodrag nopan">
      {#if data.editorHref}
        <a class="teacher-flow-unit-node__popover-action" href={data.editorHref} onclick={stopPropagation}>
          Inhalt bearbeiten
        </a>
      {/if}
      {#if data.quickHref}
        <a class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" href={data.quickHref} onclick={stopPropagation}>
          Bearbeiten
        </a>
      {/if}
      {#if data.createHref}
        <a class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" href={data.createHref} onclick={stopPropagation}>
          {data.createLabel}
        </a>
      {/if}
    </div>
  {/if}
</div>
