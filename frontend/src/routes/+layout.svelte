<script lang="ts">
  import { page } from "$app/state";
  import "@fontsource/nunito/400.css";
  import "@fontsource/nunito/600.css";
  import "@fontsource/nunito/700.css";
  import "$lib/styles/app.css";
  import type { Snippet } from "svelte";
  import type { BreadcrumbItem } from "$lib/types/navigation";
  import type { LayoutData } from "./$types";

  let { data, children }: { data: LayoutData; children: Snippet } = $props();
  let accountMenu = $state<HTMLDetailsElement | null>(null);

  const learnerNavItems = [
    {
      href: "/learning",
      label: "Lernraum",
      requiredSpace: "learning"
    }
  ];

  const teacherNavItems = [
    {
      href: "/teaching/courses",
      label: "Kurse",
      requiredSpace: "teaching"
    },
    {
      href: "/teaching/units",
      label: "Lerneinheiten",
      requiredSpace: "teaching"
    },
    {
      href: "/diagnostics",
      label: "Diagnostik",
      requiredSpace: "diagnostics"
    },
    {
      href: "/live",
      label: "Live",
      requiredSpace: "live"
    }
  ];

  function primaryNavItems() {
    return data.bootstrap?.user.role === "student" ? learnerNavItems : teacherNavItems;
  }

  function isActive(href: string): boolean {
    const pathname = page.url.pathname;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function isPrimaryActive(href: string): boolean {
    if (href === "/teaching/courses") {
      return isActive("/teaching/courses");
    }

    if (href === "/teaching/units") {
      return isActive("/teaching/units");
    }

    return isActive(href);
  }

  function currentLabel(): string {
    if (page.url.pathname === "/") {
      return "Start";
    }

    return primaryNavItems().find((item) => isPrimaryActive(item.href))?.label ?? "GUSTAV";
  }

  function currentCopy(): string {
    if (page.url.pathname === "/") {
      return "Die neue Oberfläche führt jede Rolle direkt in den passenden Arbeitsraum.";
    }

    if (isActive("/learning")) {
      return "Ruhige Arbeitsflächen für Inhalte, Aufgaben und Rückmeldungen.";
    }

    if (isActive("/teaching")) {
      return "Operative Sicht auf Kurse, Einheiten und nächste Schritte.";
    }

    if (isActive("/diagnostics")) {
      return "Scanbare Analytik mit klaren Drilldowns in Kurs- und Lernendenansichten.";
    }

    if (isActive("/live")) {
      return "Schnelle Orientierung für Unterrichtsmomente mit hohem Takt.";
    }

    return "Ein Produkt, klare Räume, wenig visuelle Ablenkung.";
  }

  function currentBreadcrumbs(): BreadcrumbItem[] {
    const breadcrumbs = page.data.breadcrumbs;
    return Array.isArray(breadcrumbs) ? (breadcrumbs as BreadcrumbItem[]) : [];
  }

  function pageTitle(): string {
    return typeof page.data.pageTitle === "string" && page.data.pageTitle.length > 0
      ? page.data.pageTitle
      : currentLabel();
  }

  function pageCopy(): string {
    return typeof page.data.pageCopy === "string" && page.data.pageCopy.length > 0
      ? page.data.pageCopy
      : currentCopy();
  }

  function closeAccountMenuOnWindowClick(event: MouseEvent): void {
    if (!accountMenu?.open) {
      return;
    }

    const target = event.target;
    if (!(target instanceof Node) || accountMenu.contains(target)) {
      return;
    }

    accountMenu.open = false;
  }
</script>

<svelte:head>
  <title>GUSTAV</title>
  <meta name="theme-color" content={data.theme === "dark" ? "#272E33" : "#FAF4ED"} />
</svelte:head>

<svelte:window onclick={closeAccountMenuOnWindowClick} />

<div class="app-shell" data-theme={data.theme}>
  <header class="app-topbar">
    <div class="app-topbar-inner">
      <a class="brand-lockup" href="/" aria-label="Startseite">
        <img class="brand-logo" src="/gustav-logo.png" alt="" />
        <div class="brand-copy">
          <strong>GUSTAV</strong>
        </div>
      </a>

      <nav class="space-nav" aria-label="Hauptnavigation">
        {#each primaryNavItems() as item}
          {#if data.bootstrap?.spaces?.includes(item.requiredSpace)}
            <a
              href={item.href}
              aria-current={isPrimaryActive(item.href) ? "page" : undefined}
              aria-label={item.label}
            >
              <span class="nav-label">{item.label}</span>
            </a>
          {/if}
        {/each}
      </nav>

      {#if data.bootstrap}
        <details class="account-menu" bind:this={accountMenu}>
          <summary class="account-trigger" aria-label="Konto-Menü">
            <span class="account-name">{data.bootstrap.user.name}</span>
            <span class="account-avatar" aria-hidden="true">
              {data.bootstrap.user.name.slice(0, 1).toUpperCase()}
            </span>
          </summary>

          <div class="account-popover">
            <p class="account-eyebrow">Angemeldet als</p>
            <strong>{data.bootstrap.user.name}</strong>
            <p class="identity-meta">{data.bootstrap.user.role}</p>
            <a class="ghost-link" href="/auth/logout">Abmelden</a>
          </div>
        </details>
      {/if}
    </div>
  </header>

  <main class="workspace-shell">
    <div class="workspace-inner">
      <header class="workspace-header">
        <div class="workspace-topbar">
          {#if currentBreadcrumbs().length}
            <nav class="workspace-breadcrumbs" aria-label="Breadcrumb">
              {#each currentBreadcrumbs() as item, index}
                {#if index > 0}
                  <span class="breadcrumb-separator" aria-hidden="true">/</span>
                {/if}

                {#if item.href}
                  <a href={item.href}>{item.label}</a>
                {:else}
                  <span class="breadcrumb-current">{item.label}</span>
                {/if}
              {/each}
            </nav>
          {/if}
        </div>

        <div class="workspace-heading">
          <h1>{pageTitle()}</h1>
          <p class="workspace-copy">{pageCopy()}</p>
        </div>
      </header>

      <div class="workspace-body">
        {@render children()}
      </div>
    </div>
  </main>
</div>
