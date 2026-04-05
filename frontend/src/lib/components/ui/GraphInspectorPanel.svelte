<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow,
    title,
    closeHref = null,
    closeLabel = "Schließen",
    children,
    footer
  }: {
    eyebrow: string;
    title: string;
    closeHref?: string | null;
    closeLabel?: string;
    children?: Snippet;
    footer?: Snippet;
  } = $props();
</script>

<aside class="graph-inspector-panel">
  <div class="graph-inspector-panel__header">
    <div>
      <p class="workspace-label">{eyebrow}</p>
      <h2>{title}</h2>
    </div>

    {#if closeHref}
      <a class="workspace-link-action workspace-link-action--subtle" href={closeHref}>{closeLabel}</a>
    {/if}
  </div>

  <div class="graph-inspector-panel__body">
    {@render children?.()}
  </div>

  {#if footer}
    <div class="graph-inspector-panel__footer">
      {@render footer()}
    </div>
  {/if}
</aside>
