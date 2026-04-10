<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    backHref = null,
    backLabel = null,
    title,
    copy = null,
    actions,
    secondary
  }: {
    backHref?: string | null;
    backLabel?: string | null;
    title: string;
    copy?: string | null;
    actions?: Snippet;
    secondary?: Snippet;
  } = $props();
</script>

<section class="page-action-head">
  <div class="page-action-head__main">
    <div class="page-action-head__copy">
      {#if backHref && backLabel}
        <a class="workspace-back-link" href={backHref}>{backLabel}</a>
      {/if}
      <h1>{title}</h1>
      {#if copy}
        <p class="page-action-head__copyline workspace-composer-copyline">{copy}</p>
      {/if}
    </div>

    {#if actions}
      <div class="page-action-head__actions">
        {@render actions()}
      </div>
    {/if}
  </div>

  {#if secondary}
    <div class="page-action-head__secondary">
      {@render secondary()}
    </div>
  {/if}
</section>
