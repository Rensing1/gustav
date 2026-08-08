<script lang="ts">
  import { goto } from "$app/navigation";
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";
  import { getContext } from "svelte";

  import type { TeacherFlowNodeData } from "$lib/graph/teacher-unit-flow";
  import {
    TEACHER_GRAPH_SELECTION_CONTEXT,
    type TeacherGraphSelectionHandler
  } from "./selection-context";

  let { id, data, selected = false }: NodeProps & { data: TeacherFlowNodeData; selected?: boolean } = $props();
  const selectGraphItem = getContext<TeacherGraphSelectionHandler | undefined>(TEACHER_GRAPH_SELECTION_CONTEXT);

  function selectNode(event: MouseEvent) {
    if (!data.selectHref) return;
    event.preventDefault();
    event.stopPropagation();
    if (selectGraphItem) {
      selectGraphItem(data.kind, id);
      return;
    }
    void goto(`${window.location.pathname}${data.selectHref}`, { keepFocus: true, noScroll: true });
  }

</script>

<div class:teacher-flow-unit-node--compact={data.compact} class:teacher-flow-unit-node--selected={selected} class="teacher-flow-unit-node">
  {#if data.connectable}
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--top-target"
      id="top-target"
      position={Position.Top}
      type="target"
      aria-label={`Eingehende Verbindung oben: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--top-source"
      id="top-source"
      position={Position.Top}
      type="source"
      aria-label={`Ausgehende Verbindung oben: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--right-target"
      id="right-target"
      position={Position.Right}
      type="target"
      aria-label={`Eingehende Verbindung rechts: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--right-source"
      id="right-source"
      position={Position.Right}
      type="source"
      aria-label={`Ausgehende Verbindung rechts: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--bottom-target"
      id="bottom-target"
      position={Position.Bottom}
      type="target"
      aria-label={`Eingehende Verbindung unten: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--bottom-source"
      id="bottom-source"
      position={Position.Bottom}
      type="source"
      aria-label={`Ausgehende Verbindung unten: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--left-target"
      id="left-target"
      position={Position.Left}
      type="target"
      aria-label={`Eingehende Verbindung links: ${data.title}`}
    />
    <Handle
      class="teacher-flow-unit-node__handle teacher-flow-unit-node__handle--left-source"
      id="left-source"
      position={Position.Left}
      type="source"
      aria-label={`Ausgehende Verbindung links: ${data.title}`}
    />
  {/if}

  <span aria-hidden="true" class="teacher-flow-unit-node__drag-handle"></span>

  {#if data.selectHref}
    <a class="teacher-flow-unit-node__copy nodrag nopan" href={data.selectHref} onclick={selectNode}>
      <div class="teacher-flow-unit-node__header">
        <div class="teacher-flow-unit-node__header-main">
          <span>{data.kicker}</span>
        </div>
      </div>
      <strong>{data.title}</strong>
      <small>{data.meta}</small>
    </a>
  {:else}
    <div class="teacher-flow-unit-node__copy">
      <div class="teacher-flow-unit-node__header">
        <div class="teacher-flow-unit-node__header-main">
          <span>{data.kicker}</span>
        </div>
      </div>
      <strong>{data.title}</strong>
      <small>{data.meta}</small>
    </div>
  {/if}

</div>
