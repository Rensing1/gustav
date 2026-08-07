<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow,
    title,
    closeHref = null,
    closeLabel = "Schließen",
    onClose,
    children,
    footer
  }: {
    eyebrow: string;
    title: string;
    closeHref?: string | null;
    closeLabel?: string;
    onClose?: (() => void) | null;
    children?: Snippet;
    footer?: Snippet;
  } = $props();

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.key === "Escape" && onClose) {
      event.preventDefault();
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<aside class="graph-inspector-panel" aria-label={title}>
  <div class="graph-inspector-panel__header">
    <div>
      <p class="workspace-label">{eyebrow}</p>
      <h2>{title}</h2>
    </div>

    {#if onClose}
      <button class="workspace-link-action workspace-link-action--subtle" type="button" onclick={onClose}>{closeLabel}</button>
    {:else if closeHref}
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
