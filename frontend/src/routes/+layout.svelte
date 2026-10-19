<script lang="ts">
  import { page } from "$app/state";
  import "@fontsource/inter/latin-500.css";
  import "@fontsource/inter/latin-600.css";
  import "@fontsource/manrope/latin-700.css";
  import "@fontsource/manrope/latin-800.css";
  import "@fontsource/nunito/latin-400.css";
  import "@fontsource/nunito/latin-600.css";
  import "@fontsource/nunito/latin-700.css";
  import "@fontsource/space-grotesk/latin-400.css";
  import "@fontsource/space-grotesk/latin-500.css";
  import "@fontsource/space-grotesk/latin-700.css";
  import "@fontsource/work-sans/latin-400.css";
  import "@fontsource/work-sans/latin-500.css";
  import "@fontsource/work-sans/latin-600.css";
  import "$lib/styles/index.css";
  import ContextNavigation from "$lib/components/ui/ContextNavigation.svelte";
  import AppHeader from "$lib/components/ui/AppHeader.svelte";
  import { syncDocumentTheme } from "$lib/theme/client";
  import { setContext, type Snippet } from "svelte";
  import { workspaceNavigationKey, type WorkspaceNavigation } from "$lib/types/workspace-navigation";
  import type { BreadcrumbItem } from "$lib/types/navigation";
  import type { ThemePreference } from "$lib/types/theme";
  import type { WorkspaceLayout } from "$lib/types/workspace-layout";
  import type { LayoutData } from "./$types";

  let { data, children }: { data: LayoutData; children: Snippet } = $props();
  const workspaceNavigation = $state<WorkspaceNavigation>({ href: null });
  setContext(workspaceNavigationKey, workspaceNavigation);
  let themeOverride = $state<ThemePreference | null>(null);
  let currentTheme = $derived<ThemePreference>(themeOverride ?? data.theme);
  let themeWriteController = $state<AbortController | null>(null);

  const learnerNavItems = [
    {
      href: "/learning",
      label: "Lernraum",
      requiredSpace: "learning"
    },
    {
      href: "/learning/practice",
      label: "Üben",
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

  function concernBoxHref(): string {
    return data.bootstrap?.user.role === "student"
      ? "/learning/kummerkasten"
      : "/teaching/kummerkasten";
  }

  function isPrimaryActive(href: string): boolean {
    if (href === "/learning") return isActive(href) && !isActive("/learning/practice") && !isActive("/learning/kummerkasten");

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
    const items = Array.isArray(breadcrumbs) ? [...breadcrumbs as BreadcrumbItem[]] : [];
    // URL state changes without a server reload inside a learning workspace.
    const workspaceUrl = workspaceNavigation.href ? new URL(workspaceNavigation.href, page.url) : page.url;
    const url = workspaceUrl.pathname === page.url.pathname ? workspaceUrl : page.url;
    const moduleId = url.searchParams.get("module");
    const graph = page.data.graph as { modules?: { id: string; title: string }[] } | null;
    const module = isLearnerUnitWorkspaceRoute() ? graph?.modules?.find((item) => item.id === moduleId) : null;
    if (module && items.length) {
      items[items.length - 1] = { ...items[items.length - 1], href: page.url.pathname };
      items.push({ label: module.title, ...(url.searchParams.has("task") ? { href: `${page.url.pathname}?module=${encodeURIComponent(module.id)}` } : {}) });
    }
    if (isLearnerUnitWorkspaceRoute() && !module && url.searchParams.has("task") && items.length) {
      items[items.length - 1] = { ...items[items.length - 1], href: page.url.pathname };
    }
    return items;
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

  function isImmersiveWorkspace(): boolean {
    return page.data.immersiveWorkspace === true;
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

  function isLearnerUnitWorkspaceRoute(): boolean {
    return /^\/learning\/courses\/[^/]+\/units\/[^/]+$/.test(page.url.pathname);
  }

  function workspaceLayout(): WorkspaceLayout {
    return page.data.workspaceLayout ?? "standard";
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
  <meta name="theme-color" content={currentTheme === "dark" ? "#15171b" : "#f6f7f9"} />
</svelte:head>



<div class:app-shell--auth-route={isAuthLayout()} class="app-shell" data-theme={currentTheme}>
  <AppHeader
    items={primaryNavItems().filter((item) => data.bootstrap?.spaces?.includes(item.requiredSpace)).map((item) => ({ ...item, active: isPrimaryActive(item.href) }))}
    name={data.bootstrap?.user.name}
    concernHref={data.bootstrap ? concernBoxHref() : undefined}
    contextItems={isActive("/learning") ? currentBreadcrumbs() : undefined}
    {currentTheme} onToggle={toggleTheme} routeKey={page.url.href}
  />

  <main class:workspace-shell--auth={isAuthLayout()} class="workspace-shell">
    <div
      class="workspace-inner"
      class:workspace-inner--auth={isAuthLayout()}
      class:workspace-inner--compact={workspaceLayout() === "compact"}
      class:workspace-inner--wide={workspaceLayout() === "wide"}
      class:workspace-inner--canvas={workspaceLayout() === "canvas"}
    >
      {#if !isAuthLayout() && (!isActive("/learning") || !hidePageHeading() || currentHeaderAction())}
        <header
          class="workspace-header unified-context-header"
          class:workspace-header--breadcrumbs-wide={isLearnerUnitWorkspaceRoute()}
          class:workspace-header--learner-unit={isLearnerUnitWorkspaceRoute()}
          class:workspace-header--immersive-workspace={isImmersiveWorkspace()}
        >
          <div class="workspace-topbar">
            {#if currentBreadcrumbs().length && !isActive("/learning")}
              <ContextNavigation items={currentBreadcrumbs()} />
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

      <div class="workspace-body" class:workspace-body--auth={isAuthLayout()}>
        {@render children()}
      </div>
    </div>
  </main>
</div>
