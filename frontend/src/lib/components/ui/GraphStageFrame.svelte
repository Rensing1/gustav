<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow,
    title,
    copy = null,
    chromeless = false,
    actions,
    children
  }: {
    eyebrow: string;
    title: string;
    copy?: string | null;
    chromeless?: boolean;
    actions?: Snippet;
    children?: Snippet;
  } = $props();
</script>

<section class:graph-stage-frame--chromeless={chromeless} class="graph-stage-frame">
  {#if !chromeless}
    <header class="graph-stage-frame__header">
      <div class="graph-stage-frame__copy">
        <p class="workspace-label">{eyebrow}</p>
        <h2>{title}</h2>
        {#if copy}
          <p class="graph-stage-frame__meta">{copy}</p>
        {/if}
      </div>

      {#if actions}
        <div class="graph-stage-frame__actions">
          {@render actions()}
        </div>
      {/if}
    </header>
  {/if}

  <div class="graph-stage-frame__body">
    {@render children?.()}
  </div>
</section>
