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
      <div class="teacher-flow-unit-node__header-main">
        <span aria-hidden="true" class="teacher-flow-unit-node__drag-handle"></span>
        <span>{data.kicker}</span>
      </div>
      <span class="teacher-flow-unit-node__state">{data.kind === "module" ? "Modul" : "Abschnitt"}</span>
      {#if data.quickHref}
        <a
          class="teacher-flow-unit-node__editor nodrag nopan"
          href={data.quickHref}
          aria-label={`Eigenschaften von ${data.title} öffnen`}
          onclick={stopPropagation}
        >
          Auswählen
        </a>
      {/if}
    </div>
    <strong>{data.title}</strong>
    <small>{data.meta}</small>
  </div>

</div>
