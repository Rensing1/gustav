<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow,
    title,
    createLabel,
    showCreate = false,
    hasItems = false,
    emptyMessage = null,
    onCreate,
    list,
    create
  }: {
    eyebrow: string;
    title: string;
    createLabel: string;
    showCreate?: boolean;
    hasItems?: boolean;
    emptyMessage?: string | null;
    onCreate?: (() => void) | null;
    list?: Snippet;
    create?: Snippet;
  } = $props();
</script>

<section class="workspace-panel teacher-node-editor-section">
  <div class="teacher-node-editor-section__header">
    <div class="teacher-node-editor-section__heading">
      <p class="workspace-label">{eyebrow}</p>
      <h2>{title}</h2>
    </div>
    <button class="teacher-node-editor-section__action" type="button" onclick={onCreate}>
      <span aria-hidden="true">+</span>
      {createLabel}
    </button>
  </div>

  {#if showCreate}
    <div class="teacher-node-editor-section__create">
      <div class="teacher-node-editor-section__create-head">
        <p class="workspace-kicker">Neu</p>
      </div>
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
