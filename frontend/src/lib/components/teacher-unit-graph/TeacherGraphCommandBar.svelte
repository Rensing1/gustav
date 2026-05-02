<script lang="ts">
  import type { Snippet } from "svelte";

  type TeacherGraphCommandBarActionBase = {
    label: string;
    active?: boolean;
  };

  export type TeacherGraphCommandBarAction =
    | (TeacherGraphCommandBarActionBase & { href: string; onClick?: never })
    | (TeacherGraphCommandBarActionBase & { href?: never; onClick: () => void });

  let {
    actions,
    popovers
  }: {
    actions: TeacherGraphCommandBarAction[];
    popovers?: Snippet;
  } = $props();
</script>

<div class="workspace-unit-commandbar-stack">
  <div class="workspace-unit-commandbar-heading">
    <p class="workspace-label">Canvas</p>
    <strong>Teacher flow</strong>
  </div>

  <div class="workspace-unit-commandbar" role="toolbar" aria-label="Graphwerkzeuge">
    {#each actions as action}
      {#if action.onClick}
        <button
          class={`workspace-top-action workspace-top-action--quiet ${action.active ? "workspace-top-action--active" : ""}`.trim()}
          type="button"
          onclick={action.onClick}
        >
          {action.label}
        </button>
      {:else}
        <a
          class={`workspace-top-action workspace-top-action--quiet ${action.active ? "workspace-top-action--active" : ""}`.trim()}
          href={action.href}
        >
          {action.label}
        </a>
      {/if}
    {/each}
  </div>

  {#if popovers}
    {@render popovers()}
  {/if}
</div>
