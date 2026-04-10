<script lang="ts">
  import { enhance } from "$app/forms";
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";

  import type { TeacherFlowNodeData } from "$lib/graph/teacher-unit-flow";

  let { id, data, selected = false }: NodeProps & { data: TeacherFlowNodeData; selected?: boolean } = $props();

  function stopPropagation(event: MouseEvent) {
    event.stopPropagation();
  }

  function openProperties(event: MouseEvent) {
    stopPropagation(event);
    data.onOpenProperties?.();
  }

  function closeProperties(event: MouseEvent) {
    stopPropagation(event);
    data.onCloseProperties?.();
  }

  const enhanceGraphForm = () => {
    return async ({ update }: { update: (options?: { reset?: boolean; invalidateAll?: boolean }) => Promise<void> }) => {
      await update({ reset: false, invalidateAll: false });
    };
  };
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
      <span class="teacher-flow-unit-node__state">Module node</span>
      {#if data.editorHref}
        <a class="teacher-flow-unit-node__editor nodrag nopan" href={data.editorHref} onclick={stopPropagation}>
          Öffnen
        </a>
      {/if}
    </div>
    <strong>{data.title}</strong>
    <small>{data.meta}</small>
  </div>

  {#if selected && !data.quickEdit && (data.onOpenProperties || data.editorHref || data.createHref)}
    <div class="teacher-flow-unit-node__popover nodrag nopan">
      {#if data.editorHref}
        <a class="teacher-flow-unit-node__popover-action" href={data.editorHref} onclick={stopPropagation}>
          Inhalt bearbeiten
        </a>
      {/if}
      {#if data.onOpenProperties}
        <button class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" type="button" onclick={openProperties}>
          Eigenschaften
        </button>
      {/if}
      {#if data.createHref}
        <a class="teacher-flow-unit-node__popover-action teacher-flow-unit-node__popover-action--subtle" href={data.createHref} onclick={stopPropagation}>
          {data.createLabel}
        </a>
      {/if}
    </div>
  {/if}

  {#if data.quickEdit}
    <aside class="teacher-flow-unit-node__quickedit nodrag nopan">
      <div class="teacher-flow-unit-node__quickedit-header">
        <div>
          <p class="workspace-label">Property inspector</p>
          <strong>Eigenschaften</strong>
        </div>
        <button class="teacher-flow-unit-node__quickedit-close" type="button" onclick={closeProperties}>
          Schließen
        </button>
      </div>

      <form method="POST" action="?/saveModule" class="teacher-flow-unit-node__quickedit-form" use:enhance={enhanceGraphForm}>
        <input type="hidden" name="module_id" value={id} />
        <input type="hidden" name="current_phase_id" value={data.phaseId ?? ""} />
        <label class="teacher-flow-unit-node__quickedit-field workspace-field">
          <span>Name</span>
          <input name="title" type="text" value={data.quickEdit.title} />
        </label>
        <label class="teacher-flow-unit-node__quickedit-field workspace-field">
          <span>Phase</span>
          <select name="phase_id">
            {#each data.quickEdit.phaseOptions as phase}
              <option selected={data.quickEdit.phaseId === phase.id} value={phase.id}>
                {phase.title}
              </option>
            {/each}
          </select>
        </label>
        <label class="teacher-flow-unit-node__quickedit-field workspace-field">
          <span>Freischaltung</span>
          <input
            name="required_prereq_count"
            type="number"
            min="0"
            value={data.quickEdit.requiredPrereqCount}
          />
        </label>
        {#if data.quickEdit.error}
          <p class="workspace-note workspace-note--error">{data.quickEdit.error}</p>
        {/if}
        <div class="teacher-flow-unit-node__quickedit-actions">
          <button class="workspace-link-action" type="submit">Speichern</button>
          {#if data.editorHref}
            <a class="workspace-link-action workspace-link-action--subtle" href={data.editorHref} onclick={stopPropagation}>
              Inhalt bearbeiten
            </a>
          {/if}
        </div>
      </form>

      <form method="POST" action="?/deleteModule" class="teacher-flow-unit-node__quickedit-delete" use:enhance={enhanceGraphForm}>
        <input type="hidden" name="module_id" value={id} />
        <button class="workspace-link-action workspace-link-action--danger" type="submit">Modul löschen</button>
      </form>
    </aside>
  {/if}
</div>
