<script lang="ts">
  import { page } from "$app/state";
  import "@fontsource/inter/500.css";
  import "@fontsource/inter/600.css";
  import "@fontsource/manrope/700.css";
  import "@fontsource/manrope/800.css";
  import "@fontsource/nunito/400.css";
  import "@fontsource/nunito/600.css";
  import "@fontsource/nunito/700.css";
  import "@fontsource/space-grotesk/400.css";
  import "@fontsource/space-grotesk/500.css";
  import "@fontsource/space-grotesk/700.css";
  import "@fontsource/work-sans/400.css";
  import "@fontsource/work-sans/500.css";
  import "@fontsource/work-sans/600.css";
  import "$lib/styles/app.css";
  import "$lib/styles/auth-theme.css";
  import "$lib/styles/design-system.css";
  import BreadcrumbBar from "$lib/components/ui/BreadcrumbBar.svelte";
  import ThemeToggle from "$lib/components/ui/ThemeToggle.svelte";
  import { syncDocumentTheme } from "$lib/theme/client";
  import type { Snippet } from "svelte";
  import type { BreadcrumbItem } from "$lib/types/navigation";
  import type { ThemePreference } from "$lib/types/theme";
  import type { LayoutData } from "./$types";

  let { data, children }: { data: LayoutData; children: Snippet } = $props();
  let accountMenu = $state<HTMLDetailsElement | null>(null);
  let themeOverride = $state<ThemePreference | null>(null);
  let currentTheme = $derived<ThemePreference>(themeOverride ?? data.theme);
  let themeWriteController = $state<AbortController | null>(null);

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
      return "";
    }

    return "Ein Produkt, klare Räume, wenig visuelle Ablenkung.";
  }

  function currentBreadcrumbs(): BreadcrumbItem[] {
    const breadcrumbs = page.data.breadcrumbs;
    return Array.isArray(breadcrumbs) ? (breadcrumbs as BreadcrumbItem[]) : [];
  }

  function currentHeaderAction(): { href: string; label: string } | null {
    const action = page.data.headerAction;
    if (!action || typeof action !== "object") {
      return null;
    }

    const href = "href" in action ? String(action.href || "") : "";
    const label = "label" in action ? String(action.label || "") : "";
    if (!href || !label) {
      return null;
    }
    return { href, label };
  }

  function hidePageHeading(): boolean {
    return page.data.hidePageHeading === true;
  }

  function isAuthLayout(): boolean {
    return page.data.authLayout === true;
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

  function isTeacherUnitWorkspaceRoute(): boolean {
    return /^\/teaching\/units\/[^/]+$/.test(page.url.pathname);
  }

  function isLearnerUnitWorkspaceRoute(): boolean {
    return /^\/learning\/courses\/[^/]+\/units\/[^/]+$/.test(page.url.pathname);
  }

  function routeRequestsWideWorkspaceShell(): boolean {
    return page.data.wideWorkspaceShell === true;
  }

  function hasWideWorkspaceShell(): boolean {
    return routeRequestsWideWorkspaceShell() || isTeacherUnitWorkspaceRoute() || isLearnerUnitWorkspaceRoute();
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

  async function toggleTheme(): Promise<void> {
    const nextTheme: ThemePreference = currentTheme === "dark" ? "light" : "dark";
    themeOverride = nextTheme;

    themeWriteController?.abort();
    const controller = new AbortController();
    themeWriteController = controller;

    try {
      const response = await fetch("/theme", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({ theme: nextTheme }),
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`theme_toggle_failed:${response.status}`);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      console.error("Failed to persist theme preference", error);
    } finally {
      if (themeWriteController === controller) {
        themeWriteController = null;
      }
    }
  }

  $effect(() => {
    if (typeof document === "undefined") {
      return;
    }

    syncDocumentTheme(document, currentTheme);
  });
</script>

<svelte:head>
  <title>GUSTAV</title>
  <meta name="theme-color" content={currentTheme === "dark" ? "#272E33" : "#FAF4ED"} />
</svelte:head>

<svelte:window onclick={closeAccountMenuOnWindowClick} />

<div class:app-shell--auth-route={isAuthLayout()} class="app-shell" data-theme={currentTheme}>
  <header class:app-topbar--learner-unit={isLearnerUnitWorkspaceRoute()} class="app-topbar">
    <div class:app-topbar-inner--learner-unit={isLearnerUnitWorkspaceRoute()} class="app-topbar-inner">
      <a class="brand-lockup" href="/" aria-label="Startseite">
        <img class="brand-logo" src="/gustav-logo.png" alt="" />
        <div class="brand-copy">
          <strong>GUSTAV</strong>
        </div>
      </a>

      {#if isLearnerUnitWorkspaceRoute() && currentBreadcrumbs().length}
        <BreadcrumbBar className="app-topbar-breadcrumbs app-topbar-breadcrumbs--learner-unit" items={currentBreadcrumbs()} />
      {:else}
        <nav class:space-nav--learner-unit={isLearnerUnitWorkspaceRoute()} class="space-nav" aria-label="Hauptnavigation">
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
      {/if}

      <div class="app-topbar-controls">
        <div class="app-topbar-tools">
          <ThemeToggle currentTheme={currentTheme} onToggle={toggleTheme} />

          {#if data.bootstrap}
            <details class="account-menu" bind:this={accountMenu}>
              <summary class="account-trigger" aria-label="Konto-Menü">
                <span class="account-trigger__name">{data.bootstrap.user.name}</span>
                <span class="account-trigger__initial" aria-hidden="true">
                  {data.bootstrap.user.name.slice(0, 1).toUpperCase()}
                </span>
              </summary>

              <div class="account-menu__panel">
                <a class="account-menu__action" href="/profile">Profil</a>
                {#if data.bootstrap.user.role === "student"}
                  <a class="account-menu__action" href="/learning/kummerkasten">Kummerkasten</a>
                {:else}
                  <a class="account-menu__action" href="/teaching/kummerkasten">Kummerkasten</a>
                {/if}
                <a class="account-menu__action" href="/auth/logout">Abmelden</a>
              </div>
            </details>
          {/if}
        </div>
      </div>
    </div>
  </header>

  <main class:workspace-shell--auth={isAuthLayout()} class="workspace-shell">
    <div
      class="workspace-inner"
      class:workspace-inner--auth={isAuthLayout()}
      class:workspace-inner--wide={hasWideWorkspaceShell()}
      class:workspace-inner--learner-unit-wide={isLearnerUnitWorkspaceRoute()}
    >
      {#if !isAuthLayout()}
        <header
          class="workspace-header"
          class:workspace-header--measure={isLearnerUnitWorkspaceRoute()}
          class:workspace-header--breadcrumbs-wide={isLearnerUnitWorkspaceRoute()}
          class:workspace-header--learner-unit={isLearnerUnitWorkspaceRoute()}
        >
          <div class="workspace-topbar">
            {#if currentBreadcrumbs().length && !isLearnerUnitWorkspaceRoute()}
              <BreadcrumbBar
                className="workspace-breadcrumbs"
                items={currentBreadcrumbs()}
              />
            {/if}

            {#if currentHeaderAction()}
              <a class="workspace-topbar-action" href={currentHeaderAction()?.href}>
                {currentHeaderAction()?.label}
              </a>
            {/if}
          </div>

          {#if !hidePageHeading()}
            <div class="workspace-heading">
              <h1>{pageTitle()}</h1>
              {#if pageCopy()}
                <p class="workspace-copy">{pageCopy()}</p>
              {/if}
            </div>
          {/if}
        </header>
      {/if}

      <div
        class="workspace-body"
        class:workspace-body--auth={isAuthLayout()}
        class:workspace-body--wide={hasWideWorkspaceShell()}
      >
        {@render children()}
      </div>
    </div>
  </main>
</div>
