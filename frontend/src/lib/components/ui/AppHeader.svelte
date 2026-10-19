<script lang="ts">
  import ContextHeaderNavigation from "./ContextHeaderNavigation.svelte";
  import type { BreadcrumbItem } from "$lib/types/navigation";
  import ThemeToggle from "./ThemeToggle.svelte";
  import type { ThemePreference } from "$lib/types/theme";
  let { items, name, concernHref, currentTheme, onToggle, routeKey, contextItems }: {
    contextItems?: BreadcrumbItem[];
    items: { href: string; label: string; active: boolean }[];
    name?: string; concernHref?: string; currentTheme: ThemePreference;
    onToggle: () => void; routeKey: string;
  } = $props();
  let menu = $state<HTMLDetailsElement>();
  let account = $state<HTMLDetailsElement>();
  $effect(() => { routeKey; if (menu) menu.open = false; if (account) account.open = false; });
  function closeOutside(event: MouseEvent) {
    if (!(event.target instanceof Node)) return;
    for (const element of [menu, account]) {
      if (element && !element.contains(event.target)) element.open = false;
    }
  }
  function closeOnEscape(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    for (const element of [menu, account]) {
      if (element?.open) { element.open = false; element.querySelector("summary")?.focus(); }
    }
  }
</script>

<svelte:window onclick={closeOutside} onkeydown={closeOnEscape} />
<header class="global-header" class:global-header--context={contextItems !== undefined}>
  <div class="global-header__inner">
    <a class="global-header__brand" href="/" aria-label="GUSTAV Startseite"><img src="/gustav-logo.png" alt="" />GUSTAV</a>
    {#if contextItems}
      <ContextHeaderNavigation items={contextItems} destinations={items} />
    {:else}
    <nav class="global-header__nav" aria-label="Hauptnavigation">
      {#each items as item}<a href={item.href} aria-current={item.active ? "page" : undefined}>{item.label}</a>{/each}
    </nav>
    {/if}
    <div class="global-header__tools">
      {#if !contextItems}
      {#if concernHref}<a class="global-header__concern" href={concernHref}>Kummerkasten</a>{/if}
      <details class="global-header__mobile-menu" bind:this={menu} ontoggle={() => { if (menu?.open && account) account.open = false; }}>
        <summary>Menü <span aria-hidden="true">☰</span></summary>
        <nav class="global-header__panel" aria-label="Mobile Hauptnavigation">
          {#each items as item}<a href={item.href} aria-current={item.active ? "page" : undefined}>{item.label}</a>{/each}
          {#if concernHref}<a href={concernHref}>Kummerkasten</a>{/if}
        </nav>
      </details>
      {/if}
      <details class="global-header__account" bind:this={account} ontoggle={() => { if (account?.open && menu) menu.open = false; }}>
        <summary aria-label="Konto-Menü"><span class="global-header__name">{name ?? "Darstellung"}</span><span class="global-header__avatar" aria-hidden="true">{name?.slice(0, 1).toUpperCase() ?? "◐"}</span></summary>
        <div class="global-header__panel">
          {#if name}<a href="/profile">Profil</a>{/if}
          {#if contextItems && concernHref}<a href={concernHref}>Kummerkasten</a>{/if}
          <div class="global-header__theme"><span>Darstellung</span><ThemeToggle {currentTheme} {onToggle} /></div>
          {#if name}<a href="/auth/logout">Abmelden</a>{/if}
        </div>
      </details>
    </div>
  </div>
</header>
