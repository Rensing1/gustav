<script lang="ts">
  import BreadcrumbBar from "./BreadcrumbBar.svelte";
  import type { BreadcrumbItem } from "$lib/types/navigation";
  let { items }: { items: BreadcrumbItem[] } = $props();
  let hierarchy = $state<HTMLDetailsElement>();
  const parent = $derived(items.filter((item) => item.href).at(-1));
  $effect(() => { items; if (hierarchy) hierarchy.open = false; });
  function closeOutside(event: MouseEvent) {
    if (event.target instanceof Node && hierarchy && !hierarchy.contains(event.target)) hierarchy.open = false;
  }
</script>
<svelte:window onclick={closeOutside} onkeydown={(event) => { if (event.key === "Escape" && hierarchy?.open) { hierarchy.open = false; hierarchy.querySelector("summary")?.focus(); } }} />
<div class="context-navigation">
  <div class="context-navigation__desktop"><BreadcrumbBar {items} reload={true} /></div>
  <div class="context-navigation__mobile">
    {#if parent}<a class="context-navigation__parent" href={parent.href} data-sveltekit-reload><span aria-hidden="true">←</span> {parent.label}</a>
    {:else}<span>{items.at(-1)?.label}</span>{/if}
    {#if items.length > 1}
      <details bind:this={hierarchy}>
        <summary aria-label="Vollständigen Navigationspfad anzeigen">···</summary>
        <div class="context-navigation__panel"><BreadcrumbBar {items} reload={true} /></div>
      </details>
    {/if}
  </div>
</div>
