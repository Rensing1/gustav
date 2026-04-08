<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow,
    title,
    meta = null,
    actions,
    secondary
  }: {
    eyebrow: string;
    title: string;
    meta?: string | null;
    actions?: Snippet;
    secondary?: Snippet;
  } = $props();
</script>

<section class="workspace-frame-header">
  <div class="workspace-frame-header__main">
    {#if eyebrow || title || meta}
      <div class="workspace-frame-header__copy">
        {#if eyebrow}
          <p class="workspace-label">{eyebrow}</p>
        {/if}
        {#if title}
          <h2>{title}</h2>
        {/if}
        {#if meta}
          <p class="workspace-frame-header__meta">{meta}</p>
        {/if}
      </div>
    {/if}

    {#if actions}
      <div class="workspace-frame-header__actions">
        {@render actions()}
      </div>
    {/if}
  </div>

  {#if secondary}
    <div class="workspace-frame-header__secondary">
      {@render secondary()}
    </div>
  {/if}
</section>
