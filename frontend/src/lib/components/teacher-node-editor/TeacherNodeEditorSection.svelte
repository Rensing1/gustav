<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow,
    title,
    createLabel,
    showCreate = false,
    hasItems = false,
    workbench = false,
    emptyMessage = null,
    onCreate,
    actions,
    list,
    create
  }: {
    eyebrow: string;
    title: string;
    createLabel: string;
    showCreate?: boolean;
    hasItems?: boolean;
    workbench?: boolean;
    emptyMessage?: string | null;
    onCreate?: (() => void) | null;
    actions?: Snippet;
    list?: Snippet;
    create?: Snippet;
  } = $props();
</script>

<section class:teacher-node-editor-section--workbench={workbench} class="workspace-panel teacher-node-editor-section">
  <div class="teacher-node-editor-section__header">
    <div class="teacher-node-editor-section__heading">
      <p class="workspace-label">{eyebrow}</p>
      <h2>{title}</h2>
    </div>
    {#if !workbench}
      <button class="teacher-node-editor-section__action" type="button" onclick={onCreate}>
        <span aria-hidden="true">+</span>
        {createLabel}
      </button>
    {:else if actions}
      <div class="teacher-node-editor-section__actions">
        {@render actions()}
      </div>
    {/if}
  </div>

  {#if showCreate}
    <div class="teacher-node-editor-section__create">
      {#if !workbench}
        <div class="teacher-node-editor-section__create-head">
          <p class="workspace-kicker">Neu</p>
        </div>
      {/if}
      <div data-testid="teacher-node-editor-create-slot">
        {#if create}
          {@render create()}
        {/if}
      </div>
    </div>
  {/if}

  {#if hasItems}
    <div class="teacher-node-editor-section__list">
      {#if list}
        {@render list()}
      {/if}
    </div>
  {:else if !showCreate && emptyMessage}
    <p class="workspace-empty">{emptyMessage}</p>
  {/if}
</section>
