<script lang="ts">
  import type { Snippet } from "svelte";

  export type TeacherGraphCommandBarAction = {
    label: string;
    href: string;
    active?: boolean;
  };

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
      <a
        class={`workspace-top-action workspace-top-action--quiet ${action.active ? "workspace-top-action--active" : ""}`.trim()}
        href={action.href}
      >
        {action.label}
      </a>
    {/each}
  </div>

  {#if popovers}
    {@render popovers()}
  {/if}
</div>
