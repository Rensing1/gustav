<script lang="ts">
  import type { BreadcrumbItem } from "$lib/types/navigation";
  let { items, destinations, teaching = false }: { teaching?: boolean; items: BreadcrumbItem[]; destinations: { href: string; label: string }[] } = $props();
  let menu = $state<HTMLDetailsElement>();
  const current = $derived(items.at(-1));
  const parent = $derived(items.filter(item => item.href).at(-1));
  // A linked last item represents the module containing the open task.
  const backLabel = $derived(teaching ? (parent?.href?.includes("/units/") ? "Lernweg" : parent?.label ?? "Übersicht") : current?.href ? "Modul" : parent?.href?.includes("/units/") ? "Lernpfad" : items.length > 2 ? "Kurs" : "Lernraum");
  $effect(() => { items; if (menu) menu.open = false; });
  function outside(event: MouseEvent) {
    if (event.target instanceof Node && menu && !menu.contains(event.target)) menu.open = false;
  }
</script>
<svelte:window onclick={outside} onkeydown={(event) => { if (event.key === "Escape" && menu?.open) { menu.open = false; menu.querySelector("summary")?.focus(); } }} />
<nav class="context-header" aria-label="Kontextnavigation">
  {#if parent}
    <a class="context-header__back" href={parent.href} data-sveltekit-reload aria-label={`Zurück zu ${parent.label}`}><span aria-hidden="true">←</span><span class="context-header__back-label">{backLabel}</span></a>
  {/if}
  <details bind:this={menu} class="context-header__location">
    <summary><span>{current?.label ?? "Lernraum"}</span><span class="context-header__chevron" aria-hidden="true">⌄</span></summary>
    <div class="context-header__panel">
      <span class="context-header__caption">{teaching ? "Unterrichten" : "Dein Lernbereich"}</span>
      {#each items as item}
        {#if item.href}<a href={item.href} data-sveltekit-reload>{item.label}</a>
        {:else}<span class="context-header__current" aria-current="page">{item.label}</span>{/if}
      {/each}
      {#if destinations.some(item => !items.some(crumb => crumb.href === item.href || crumb.label === item.label))}
        <hr />
        {#each destinations.filter(item => !items.some(crumb => crumb.href === item.href || crumb.label === item.label)) as item}<a href={item.href}>{item.label}</a>{/each}
      {/if}
    </div>
  </details>
</nav>
