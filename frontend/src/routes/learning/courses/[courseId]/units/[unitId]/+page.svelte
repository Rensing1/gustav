<script lang="ts">
  import { browser } from "$app/environment";
  import { Controls, SvelteFlow } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";
  import { onMount } from "svelte";

  import LearningGraphNode from "$lib/components/learning-unit/LearningGraphNode.svelte";
  import LearningMaterialCard from "$lib/components/learning-unit/LearningMaterialCard.svelte";
  import LearningTaskCard from "$lib/components/learning-unit/LearningTaskCard.svelte";
  import GraphPhaseBand from "$lib/components/teacher-unit-graph/GraphPhaseBand.svelte";
  import TeacherGraphEdge from "$lib/components/teacher-unit-graph/TeacherGraphEdge.svelte";
  import {
    buildLearningUnitFlow,
    type LearningFlowNode
  } from "$lib/graph/learning-unit-flow";
  import type {
    LearningModuleContent,
    LearningSection,
    LearningUnitGraphModule
  } from "$lib/types/learning";
  import type { TeacherFlowEdge } from "$lib/graph/teacher-unit-flow";
  import type { ActionData, PageData } from "./$types";

  type WorkspaceViewMode = "overview" | "content";
  type ModularWorkspaceState = {
    view: WorkspaceViewMode;
    openTabs: string[];
    activeTab: string | null;
  };

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const nodeTypes = {
    unitNode: LearningGraphNode,
    phaseBand: GraphPhaseBand
  };

  const edgeTypes = {
    teacherEdge: TeacherGraphEdge
  };

  let flowNodes = $state.raw<LearningFlowNode[]>([]);
  let flowEdges = $state.raw<TeacherFlowEdge[]>([]);
  let graphBusy = $state(false);
  let modularWorkspace = $state<ModularWorkspaceState>({
    view: "overview",
    openTabs: [],
    activeTab: null
  });
  let moduleCache = $state.raw<Record<string, LearningModuleContent>>({});
  let moduleLoading = $state.raw<Record<string, boolean>>({});
  let moduleErrors = $state.raw<Record<string, string | null>>({});
  let modularWorkspaceReady = $state(false);

  let rebuildToken = 0;

  function isModularUnit(): boolean {
    return data.selectedUnit?.unit.unit_type === "modular";
  }

  function storageKey(): string {
    return `gustav.learning.unit-workspace:${data.courseId}:${data.unitId}`;
  }

  function plainModule(module: LearningModuleContent): LearningModuleContent {
    return JSON.parse(JSON.stringify(module)) as LearningModuleContent;
  }

  function defaultModularWorkspaceState(): ModularWorkspaceState {
    return {
      view: "overview",
      openTabs: [],
      activeTab: null
    };
  }

  function graphModuleById(moduleId: string | null): LearningUnitGraphModule | null {
    if (!moduleId) {
      return null;
    }
    return data.graph?.modules.find((module) => module.id === moduleId) ?? null;
  }

  function openableModuleIds(): Set<string> {
    return new Set(
      (data.graph?.modules ?? [])
        .filter((module) => module.status === "open" || module.status === "done")
        .map((module) => module.id)
    );
  }

  function normalizeModularWorkspaceState(raw: unknown): ModularWorkspaceState {
    const allowed = openableModuleIds();
    if (!raw || typeof raw !== "object") {
      return defaultModularWorkspaceState();
    }

    const candidate = raw as Partial<ModularWorkspaceState>;
    const openTabs = Array.isArray(candidate.openTabs)
      ? candidate.openTabs.map(String).filter((moduleId) => allowed.has(moduleId))
      : [];
    const activeTab = candidate.activeTab && openTabs.includes(String(candidate.activeTab))
      ? String(candidate.activeTab)
      : openTabs[0] ?? null;

    return {
      view: candidate.view === "content" ? "content" : "overview",
      openTabs,
      activeTab
    };
  }

  function readModularWorkspaceState(): ModularWorkspaceState {
    if (!browser) {
      return defaultModularWorkspaceState();
    }
    try {
      const raw = window.localStorage.getItem(storageKey());
      return normalizeModularWorkspaceState(raw ? JSON.parse(raw) : null);
    } catch {
      return defaultModularWorkspaceState();
    }
  }

  function seedModularWorkspaceState(base: ModularWorkspaceState): ModularWorkspaceState {
    const seeded = normalizeModularWorkspaceState(base);
    if (!data.activeModule) {
      return seeded;
    }

    const activeModuleId = data.activeModule.module.id;
    const openTabs = seeded.openTabs.includes(activeModuleId)
      ? seeded.openTabs
      : [...seeded.openTabs, activeModuleId];

    return {
      view: "content",
      openTabs,
      activeTab: activeModuleId
    };
  }

  function currentActiveModule(): LearningModuleContent | null {
    const moduleId = modularWorkspace.activeTab;
    return moduleId ? moduleCache[moduleId] ?? null : null;
  }

  function currentActiveModuleSummary(): LearningUnitGraphModule | null {
    return graphModuleById(modularWorkspace.activeTab);
  }

  function openTabModules(): LearningUnitGraphModule[] {
    return modularWorkspace.openTabs
      .map((moduleId) => graphModuleById(moduleId))
      .filter((module): module is LearningUnitGraphModule => Boolean(module));
  }

  function isHistoryOpen(taskId: string): boolean {
    return data.historyTaskId === taskId;
  }

  function historyHref(taskId: string, moduleId: string | null): string {
    const params = new URLSearchParams();
    params.set("history", taskId);
    if (moduleId) {
      params.set("module", moduleId);
    }
    return `?${params.toString()}#task-${taskId}`;
  }

  function syncModuleUrl(moduleId: string | null) {
    if (!browser) {
      return;
    }

    const next = new URL(window.location.href);
    if (moduleId) {
      next.searchParams.set("module", moduleId);
    } else {
      next.searchParams.delete("module");
    }
    next.searchParams.delete("history");
    next.searchParams.delete("submitted");
    next.searchParams.delete("message");
    const query = next.searchParams.toString();
    const href = query ? `${next.pathname}?${query}` : next.pathname;
    window.history.replaceState(window.history.state, "", href);
  }

  async function ensureModuleLoaded(moduleId: string) {
    if (!browser || moduleCache[moduleId] || moduleLoading[moduleId]) {
      return;
    }

    moduleLoading = { ...moduleLoading, [moduleId]: true };
    moduleErrors = { ...moduleErrors, [moduleId]: null };

    try {
      const response = await fetch(
        `/learning/courses/${encodeURIComponent(data.courseId)}/units/${encodeURIComponent(data.unitId)}/modules/${encodeURIComponent(moduleId)}?include=materials,tasks`,
        {
          credentials: "include",
          cache: "no-store"
        }
      );

      if (!response.ok) {
        throw new Error(`module_fetch_failed_${response.status}`);
      }

      const payload = (await response.json()) as LearningModuleContent;
      moduleCache = {
        ...moduleCache,
        [moduleId]: plainModule(payload)
      };
    } catch {
      moduleErrors = {
        ...moduleErrors,
        [moduleId]: "Das Modul konnte nicht geladen werden."
      };
    } finally {
      moduleLoading = {
        ...moduleLoading,
        [moduleId]: false
      };
    }
  }

  function setWorkspaceState(next: ModularWorkspaceState) {
    modularWorkspace = next;
  }

  function openModule(moduleId: string) {
    const module = graphModuleById(moduleId);
    if (!module || (module.status !== "open" && module.status !== "done")) {
      return;
    }

    const openTabs = modularWorkspace.openTabs.includes(moduleId)
      ? modularWorkspace.openTabs
      : [...modularWorkspace.openTabs, moduleId];

    setWorkspaceState({
      view: "content",
      openTabs,
      activeTab: moduleId
    });
    syncModuleUrl(moduleId);
    void ensureModuleLoaded(moduleId);
  }

  function activateTab(moduleId: string) {
    if (!modularWorkspace.openTabs.includes(moduleId)) {
      openModule(moduleId);
      return;
    }

    setWorkspaceState({
      ...modularWorkspace,
      view: "content",
      activeTab: moduleId
    });
    syncModuleUrl(moduleId);
    void ensureModuleLoaded(moduleId);
  }

  function closeTab(event: MouseEvent, moduleId: string) {
    event.preventDefault();
    event.stopPropagation();

    const currentIndex = modularWorkspace.openTabs.indexOf(moduleId);
    const remaining = modularWorkspace.openTabs.filter((tabId) => tabId !== moduleId);
    const nextActive =
      modularWorkspace.activeTab === moduleId
        ? remaining[Math.max(0, currentIndex - 1)] ?? remaining[0] ?? null
        : modularWorkspace.activeTab;

    setWorkspaceState({
      ...modularWorkspace,
      openTabs: remaining,
      activeTab: nextActive
    });
    syncModuleUrl(nextActive);
  }

  function switchView(view: WorkspaceViewMode) {
    setWorkspaceState({
      ...modularWorkspace,
      view
    });
  }

  async function rebuildGraph() {
    if (!isModularUnit() || !data.graph || !data.user) {
      flowNodes = [];
      flowEdges = [];
      return;
    }

    const token = ++rebuildToken;
    graphBusy = true;

    try {
      const flow = await buildLearningUnitFlow(
        data.graph,
        data.user,
        modularWorkspace.view === "overview" ? null : modularWorkspace.activeTab,
        openModule
      );

      if (token !== rebuildToken) {
        return;
      }

      flowNodes = flow.nodes;
      flowEdges = flow.edges;
    } finally {
      if (token === rebuildToken) {
        graphBusy = false;
      }
    }
  }

  onMount(() => {
    if (!isModularUnit()) {
      return;
    }

    if (data.activeModule) {
      moduleCache = {
        [data.activeModule.module.id]: plainModule(data.activeModule)
      };
    }

    setWorkspaceState(seedModularWorkspaceState(readModularWorkspaceState()));
    modularWorkspaceReady = true;

    if (modularWorkspace.activeTab) {
      void ensureModuleLoaded(modularWorkspace.activeTab);
    }
  });

  $effect(() => {
    if (!browser || !isModularUnit() || !modularWorkspaceReady) {
      return;
    }

    window.localStorage.setItem(storageKey(), JSON.stringify(modularWorkspace));
  });

  $effect(() => {
    if (!isModularUnit() || !modularWorkspaceReady) {
      return;
    }

    void rebuildGraph();
  });

  $effect(() => {
    if (!isModularUnit() || !modularWorkspaceReady || !modularWorkspace.activeTab) {
      return;
    }

    void ensureModuleLoaded(modularWorkspace.activeTab);
  });
</script>

<svelte:head>
  <title>{data.selectedUnit?.unit.title ?? "Lernraum"} | GUSTAV</title>
</svelte:head>

<div class="workspace-page learning-unit-space">
  <section class="learning-home-header learning-unit-header">
    <h2>{data.selectedUnit?.unit.title}</h2>
  </section>

  {#if data.message === "submitted"}
    <p class="flash flash-success learning-unit-flash">Abgabe gespeichert.</p>
  {/if}

  {#if form?.message}
    <p class="flash flash-error learning-unit-flash">{form.message}</p>
  {/if}

  {#if isModularUnit()}
    <section class="workspace-panel learning-unit-toolbar">
      <div class="workspace-tabs">
        <div class="workspace-tab-group">
          <button
            class:workspace-tab--active={modularWorkspace.view === "overview"}
            class="workspace-tab learning-unit-mode-tab"
            type="button"
            onclick={() => switchView("overview")}
          >
            Übersicht
          </button>
          <button
            class:workspace-tab--active={modularWorkspace.view === "content"}
            class="workspace-tab learning-unit-mode-tab"
            type="button"
            onclick={() => switchView("content")}
          >
            Inhalte
          </button>
        </div>
      </div>

      {#if openTabModules().length}
        <nav class="learning-unit-open-tabs" aria-label="Offene Module">
          {#each openTabModules() as module}
            <div
              class:learning-unit-open-tab--active={modularWorkspace.activeTab === module.id}
              class="learning-unit-open-tab"
            >
              <button class="learning-unit-open-tab__trigger" type="button" onclick={() => activateTab(module.id)}>
                <span class={`learning-unit-open-tab__dot learning-unit-open-tab__dot--${module.status}`}></span>
                <span class="learning-unit-open-tab__title">{module.title}</span>
              </button>
              <button class="learning-unit-open-tab__close" type="button" aria-label={`Modul ${module.title} schließen`} onclick={(event) => closeTab(event, module.id)}>
                ×
              </button>
            </div>
          {/each}
        </nav>
      {/if}
    </section>

    {#if modularWorkspace.view === "overview"}
      <section class="learning-unit-stage learning-unit-stage--graph teacher-flow-workspace teacher-flow-shell learning-flow-shell">
        {#if data.graph}
          <SvelteFlow
            bind:nodes={flowNodes}
            bind:edges={flowEdges}
            class="teacher-flow-canvas"
            {nodeTypes}
            {edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.24, minZoom: 0.68, maxZoom: 1.02 }}
            minZoom={0.52}
            maxZoom={1.26}
            elementsSelectable={false}
            nodesFocusable={false}
            panOnDrag={true}
            selectNodesOnDrag={false}
            nodesDraggable={false}
          >
            <Controls position="bottom-right" />
          </SvelteFlow>
        {:else}
          <p class="learning-unit-empty-copy">Der Graph konnte nicht geladen werden.</p>
        {/if}
      </section>
    {:else}
      <section class="learning-unit-stage learning-unit-stage--content">
        {#if currentActiveModule()}
          <section class="workspace-panel learning-unit-module-panel">
            <header class="learning-unit-module-panel__header">
              <div class="learning-unit-module-panel__copy">
                <p class="workspace-label">Modul</p>
                <h3>{currentActiveModule()?.module.title}</h3>
              </div>
              {#if currentActiveModuleSummary()}
                <p class="learning-unit-module-panel__meta">
                  {currentActiveModuleSummary()?.tasks_done}/{currentActiveModuleSummary()?.tasks_total} Aufgaben · {currentActiveModuleSummary()?.materials_count} Materialien
                </p>
              {/if}
            </header>

            <div class="learning-unit-stack">
              {#each currentActiveModule()?.materials ?? [] as material}
                <LearningMaterialCard {material} />
              {/each}

              {#each currentActiveModule()?.tasks ?? [] as task}
                <LearningTaskCard
                  courseId={data.courseId}
                  {task}
                  unitType="modular"
                  moduleId={currentActiveModule()?.module.id ?? null}
                  historyHref={historyHref(task.id, currentActiveModule()?.module.id ?? null)}
                  historyOpen={isHistoryOpen(task.id)}
                  history={data.history}
                />
              {/each}
            </div>
          </section>
        {:else if modularWorkspace.activeTab && moduleLoading[modularWorkspace.activeTab]}
          <section class="workspace-panel learning-unit-empty-state">
            <p class="learning-unit-empty-copy">Modul wird geladen …</p>
          </section>
        {:else if modularWorkspace.activeTab && moduleErrors[modularWorkspace.activeTab]}
          <section class="workspace-panel learning-unit-empty-state">
            <p class="workspace-note workspace-note--error">{moduleErrors[modularWorkspace.activeTab]}</p>
            <button
              class="workspace-top-action workspace-top-action--quiet"
              type="button"
              onclick={() => {
                if (modularWorkspace.activeTab) {
                  void ensureModuleLoaded(modularWorkspace.activeTab);
                }
              }}
            >
              Erneut versuchen
            </button>
          </section>
        {:else}
          <section class="workspace-panel learning-unit-empty-state">
            <p class="learning-unit-empty-copy">Öffne im Graphen ein verfügbares Modul, um mit den Inhalten zu arbeiten.</p>
          </section>
        {/if}
      </section>
    {/if}
  {:else}
    <section class="learning-unit-stage learning-unit-stage--content">
      <div class="learning-unit-sections">
        {#each data.sections as section}
          <section class="workspace-panel learning-unit-section">
            <header class="learning-unit-section__header">
              <div class="learning-unit-section__copy">
                <p class="workspace-label">Abschnitt {section.section.position}</p>
                <h3>{section.section.title}</h3>
              </div>
            </header>

            {#if !section.materials.length && !section.tasks.length}
              <p class="learning-unit-empty-copy">Noch keine Inhalte freigeschaltet.</p>
            {/if}

            <div class="learning-unit-stack">
              {#each section.materials as material}
                <LearningMaterialCard {material} />
              {/each}

              {#each section.tasks as task}
                <LearningTaskCard
                  courseId={data.courseId}
                  {task}
                  unitType="linear"
                  historyHref={historyHref(task.id, null)}
                  historyOpen={isHistoryOpen(task.id)}
                  history={data.history}
                />
              {/each}
            </div>
          </section>
        {/each}
      </div>
    </section>
  {/if}
</div>
