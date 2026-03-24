<script lang="ts">
  import { page } from "$app/state";
  import "@fontsource/nunito/400.css";
  import "@fontsource/nunito/600.css";
  import "@fontsource/nunito/700.css";
  import "$lib/styles/app.css";
  import type { Snippet } from "svelte";
  import type { LayoutData } from "./$types";

  let { data, children }: { data: LayoutData; children: Snippet } = $props();

  const navItems = [
    {
      href: "/learning",
      label: "Lernraum",
      requiredSpace: "learning"
    },
    {
      href: "/teaching",
      label: "Lehrenden-Welt",
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

  function isActive(href: string): boolean {
    const pathname = page.url.pathname;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function currentLabel(): string {
    if (page.url.pathname === "/") {
      return "Start";
    }

    return navItems.find((item) => isActive(item.href))?.label ?? "GUSTAV";
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
</script>

<svelte:head>
  <title>GUSTAV</title>
  <meta name="theme-color" content={data.theme === "dark" ? "#272E33" : "#FAF4ED"} />
</svelte:head>

<div class="app-shell" data-theme={data.theme}>
  <header class="app-topbar">
    <div class="app-topbar-inner">
      <a class="brand-mark" href="/" aria-label="Startseite">G</a>

      <div class="brand-copy">
        <strong>GUSTAV</strong>
      </div>

      <nav class="space-nav" aria-label="Hauptnavigation">
        {#each navItems as item}
          {#if data.bootstrap?.spaces?.includes(item.requiredSpace)}
            <a
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              aria-label={item.label}
            >
              <span class="nav-label">{item.label}</span>
            </a>
          {/if}
        {/each}
      </nav>

      {#if data.bootstrap}
        <div class="topbar-actions">
          <div class="identity-card">
            <strong>{data.bootstrap.user.name}</strong>
            <p class="identity-meta">{data.bootstrap.user.role}</p>
          </div>

          <a class="ghost-link" href="/auth/logout">Abmelden</a>
        </div>
      {/if}
    </div>
  </header>

  <main class="workspace-shell">
    <div class="workspace-inner">
      <header class="workspace-header">
        <div class="workspace-topbar">
          <nav class="workspace-breadcrumbs" aria-label="Breadcrumb" hidden></nav>
        </div>

        <div class="workspace-heading">
          <h1>{currentLabel()}</h1>
          <p class="workspace-copy">{currentCopy()}</p>
        </div>
      </header>

      <div class="workspace-body">
        {@render children()}
      </div>
    </div>
  </main>
</div>
