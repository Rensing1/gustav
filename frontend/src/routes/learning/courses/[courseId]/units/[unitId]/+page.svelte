<script lang="ts">
  import { browser } from "$app/environment";
  import { onMount, tick } from "svelte";

  import LearningUnitContentWorkspace from "$lib/components/learning-unit/LearningUnitContentWorkspace.svelte";
  import LearningUnitOverview from "$lib/components/learning-unit/LearningUnitOverview.svelte";
  import {
    buildLearningUnitFlow,
    type LearningFlowNode
  } from "$lib/graph/learning-unit-flow";
  import {
    contentGroupsForModules,
    contentGroupsForSections,
    flattenContentGroups,
    normalizePaneStacks,
    orderedOpenModules,
    reconcilePaneStacks,
    type ContentGroup,
    type LearningContentItem,
    type PaneId,
    type PaneStackEntry,
    type PaneStacks
  } from "$lib/learning-unit/workspace";
  import type { TeacherFlowEdge } from "$lib/graph/teacher-unit-flow";
  import type {
    LearningModuleContent,
    LearningUnitGraphModule
  } from "$lib/types/learning";
  import type { ActionData, PageData } from "./$types";

  type WorkspaceViewMode = "overview" | "content";
  type ModularWorkspaceState = {
    view: WorkspaceViewMode;
    openTabs: string[];
    activeTab: string | null;
    splitView: boolean;
    tocOpen: boolean;
    activePane: PaneId;
    paneStacks: PaneStacks | null;
    submissionFocus: Record<PaneId, string | null>;
  };
  type LinearWorkspaceState = {
    splitView: boolean;
    tocOpen: boolean;
    activePane: PaneId;
    paneStacks: PaneStacks | null;
    submissionFocus: Record<PaneId, string | null>;
  };
  type StoredWorkspaceState = {
    version: 5;
    modular?: Partial<ModularWorkspaceState>;
    linear?: Partial<LinearWorkspaceState>;
  };

  let { data, form }: { data: PageData; form: ActionData } = $props();

  let flowNodes = $state.raw<LearningFlowNode[]>([]);
  let flowEdges = $state.raw<TeacherFlowEdge[]>([]);
  let graphBusy = $state(false);
  let modularWorkspace = $state<ModularWorkspaceState>(defaultModularWorkspaceState());
  let linearWorkspace = $state<LinearWorkspaceState>(defaultLinearWorkspaceState());
  let moduleCache = $state.raw<Record<string, LearningModuleContent>>({});
  let moduleLoading = $state.raw<Record<string, boolean>>({});
  let moduleErrors = $state.raw<Record<string, string | null>>({});
  let workspaceReady = $state(false);
  let historyRestored = $state(false);

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
      activeTab: null,
      splitView: false,
      tocOpen: true,
      activePane: "left",
      paneStacks: null,
      submissionFocus: { left: null, right: null }
    };
  }

  function defaultLinearWorkspaceState(): LinearWorkspaceState {
    return {
      splitView: false,
      tocOpen: true,
      activePane: "left",
      paneStacks: null,
      submissionFocus: { left: null, right: null }
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
    const candidate = raw && typeof raw === "object" ? (raw as Partial<ModularWorkspaceState>) : {};
    const openTabs = Array.isArray(candidate.openTabs)
      ? candidate.openTabs.map(String).filter((moduleId) => allowed.has(moduleId))
      : [];
    const activeTab =
      candidate.activeTab && openTabs.includes(String(candidate.activeTab))
        ? String(candidate.activeTab)
        : openTabs[0] ?? null;

    return {
      view: candidate.view === "content" ? "content" : "overview",
      openTabs,
      activeTab,
      splitView: Boolean(candidate.splitView),
      tocOpen: candidate.tocOpen !== false,
      activePane: candidate.activePane === "right" ? "right" : "left",
      paneStacks: normalizePaneStacks(candidate.paneStacks),
      submissionFocus: {
        left:
          candidate.submissionFocus && typeof candidate.submissionFocus.left === "string"
            ? candidate.submissionFocus.left
            : null,
        right:
          candidate.submissionFocus && typeof candidate.submissionFocus.right === "string"
            ? candidate.submissionFocus.right
            : null
      }
    };
  }

  function normalizeLinearWorkspaceState(raw: unknown): LinearWorkspaceState {
    const candidate = raw && typeof raw === "object" ? (raw as Partial<LinearWorkspaceState>) : {};
    return {
      splitView: Boolean(candidate.splitView),
      tocOpen: candidate.tocOpen !== false,
      activePane: candidate.activePane === "right" ? "right" : "left",
      paneStacks: normalizePaneStacks(candidate.paneStacks),
      submissionFocus: {
        left:
          candidate.submissionFocus && typeof candidate.submissionFocus.left === "string"
            ? candidate.submissionFocus.left
            : null,
        right:
          candidate.submissionFocus && typeof candidate.submissionFocus.right === "string"
            ? candidate.submissionFocus.right
            : null
      }
    };
  }

  function readStoredWorkspaceState(): { modular: ModularWorkspaceState; linear: LinearWorkspaceState } {
    if (!browser) {
      return {
        modular: defaultModularWorkspaceState(),
        linear: defaultLinearWorkspaceState()
      };
    }

    try {
      const raw = window.localStorage.getItem(storageKey());
      if (!raw) {
        return {
          modular: defaultModularWorkspaceState(),
          linear: defaultLinearWorkspaceState()
        };
      }

      const parsed = JSON.parse(raw) as StoredWorkspaceState | Partial<ModularWorkspaceState>;
      if (
        parsed &&
        typeof parsed === "object" &&
        "version" in parsed &&
        parsed.version === 5 &&
        ("modular" in parsed || "linear" in parsed)
      ) {
        return {
          modular: normalizeModularWorkspaceState(parsed.modular ?? null),
          linear: normalizeLinearWorkspaceState(parsed.linear ?? null)
        };
      }

      return {
        modular: normalizeModularWorkspaceState(parsed),
        linear: defaultLinearWorkspaceState()
      };
    } catch {
      return {
        modular: defaultModularWorkspaceState(),
        linear: defaultLinearWorkspaceState()
      };
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
      ...seeded,
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

  function orderedOpenModulesForContent(): LearningUnitGraphModule[] {
    return orderedOpenModules(data.graph, modularWorkspace.openTabs);
  }

  function openTabModules(): LearningUnitGraphModule[] {
    return orderedOpenModulesForContent();
  }

  function contentGroups(): ContentGroup[] {
    if (isModularUnit()) {
      return contentGroupsForModules(data.graph, modularWorkspace.openTabs, moduleCache);
    }

    return contentGroupsForSections(data.sections);
  }

  function currentContentItems(): LearningContentItem[] {
    return flattenContentGroups(contentGroups());
  }

  function currentPaneStacks(): PaneStacks {
    const items = currentContentItems();
    const itemKeys = items.map((item) => item.key);
    const source = isModularUnit() ? modularWorkspace.paneStacks : linearWorkspace.paneStacks;

    return reconcilePaneStacks(source, itemKeys, workspaceSplitView());
  }

  function workspaceSplitView(): boolean {
    return isModularUnit() ? modularWorkspace.splitView : linearWorkspace.splitView;
  }

  function workspaceTocOpen(): boolean {
    return isModularUnit() ? modularWorkspace.tocOpen : linearWorkspace.tocOpen;
  }

  function workspaceActivePane(): PaneId {
    return workspaceSplitView()
      ? isModularUnit()
        ? modularWorkspace.activePane
        : linearWorkspace.activePane
      : "left";
  }

  function workspaceSubmissionFocus(): Record<PaneId, string | null> {
    return isModularUnit() ? modularWorkspace.submissionFocus : linearWorkspace.submissionFocus;
  }

  function visiblePaneIds(): PaneId[] {
    return workspaceSplitView() ? ["left", "right"] : ["left"];
  }

  function taskItemKey(taskId: string): string {
    return `task:${taskId}`;
  }

  function sanitizeDomToken(raw: string): string {
    return raw.replace(/[^a-zA-Z0-9_-]+/g, "-");
  }

  function itemDomId(paneId: PaneId, itemKey: string): string {
    return `learning-item-${paneId}-${sanitizeDomToken(itemKey)}`;
  }

  function itemIsOpenInPane(itemKey: string, paneId: PaneId): boolean {
    return currentPaneStacks()[paneId].some((entry) => entry.key === itemKey);
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

  function setModularWorkspaceState(next: ModularWorkspaceState) {
    modularWorkspace = next;
  }

  function setLinearWorkspaceState(next: LinearWorkspaceState) {
    linearWorkspace = next;
  }

  function setActivePane(paneId: PaneId) {
    if (!workspaceSplitView() || workspaceActivePane() === paneId) {
      return;
    }

    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        activePane: paneId
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      activePane: paneId
    });
  }

  function setSplitView(nextValue: boolean) {
    const currentStacks = currentPaneStacks();
    const nextStacks =
      nextValue && !workspaceSplitView()
        ? {
            left: [...currentStacks.left],
            right: currentStacks.right.length ? [...currentStacks.right] : [...currentStacks.left]
          }
        : currentStacks;

    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        splitView: nextValue,
        activePane: nextValue ? modularWorkspace.activePane : "left",
        paneStacks: nextStacks,
        submissionFocus: nextValue
          ? modularWorkspace.submissionFocus
          : { left: modularWorkspace.submissionFocus.left, right: null }
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      splitView: nextValue,
      activePane: nextValue ? linearWorkspace.activePane : "left",
      paneStacks: nextStacks,
      submissionFocus: nextValue
        ? linearWorkspace.submissionFocus
        : { left: linearWorkspace.submissionFocus.left, right: null }
    });
  }

  function toggleToc() {
    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        tocOpen: !modularWorkspace.tocOpen
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      tocOpen: !linearWorkspace.tocOpen
    });
  }

  function updateCurrentPaneStacks(mutator: (stacks: PaneStacks) => PaneStacks) {
    if (isModularUnit()) {
      const nextStacks = mutator(currentPaneStacks());
      setModularWorkspaceState({
        ...modularWorkspace,
        paneStacks: nextStacks
      });
      return;
    }

    const nextStacks = mutator(currentPaneStacks());
    setLinearWorkspaceState({
      ...linearWorkspace,
      paneStacks: nextStacks
    });
  }

  async function scrollToItem(paneId: PaneId, itemKey: string) {
    if (!browser) {
      return;
    }
    await tick();
    document.getElementById(itemDomId(paneId, itemKey))?.scrollIntoView({
      block: "start",
      behavior: "smooth"
    });
  }

  function openItemInPane(
    itemKey: string,
    paneId: PaneId,
    options: { activatePane?: boolean; scroll?: boolean } = {}
  ) {
    const targetPane = workspaceSplitView() ? paneId : "left";
    updateCurrentPaneStacks((stacks) => {
      const existing = stacks[targetPane];
      const index = existing.findIndex((entry) => entry.key === itemKey);
      if (index >= 0) {
        const nextEntries = [...existing];
        nextEntries[index] = { ...nextEntries[index], expanded: true };
        return {
          ...stacks,
          [targetPane]: nextEntries
        };
      }
      return {
        ...stacks,
        [targetPane]: [...existing, { key: itemKey, expanded: true }]
      };
    });

    if (options.activatePane !== false) {
      setActivePane(targetPane);
    }
    setSubmissionWorkspace(targetPane, null);
    if (options.scroll !== false) {
      void scrollToItem(targetPane, itemKey);
    }
  }

  function openItemFromToc(itemKey: string) {
    if (!itemIsOpenInPane(itemKey, workspaceActivePane())) {
      openItemInPane(itemKey, workspaceActivePane(), {
        activatePane: true,
        scroll: true
      });
      return;
    }
    void scrollToItem(workspaceActivePane(), itemKey);
  }

  function togglePaneItem(paneId: PaneId, itemKey: string) {
    updateCurrentPaneStacks((stacks) => ({
      ...stacks,
      [paneId]: stacks[paneId].map((entry) =>
        entry.key === itemKey ? { ...entry, expanded: !entry.expanded } : entry
      )
    }));
  }

  function setSubmissionWorkspace(paneId: PaneId, itemKey: string | null) {
    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        submissionFocus: {
          ...modularWorkspace.submissionFocus,
          [paneId]: itemKey
        }
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      submissionFocus: {
        ...linearWorkspace.submissionFocus,
        [paneId]: itemKey
      }
    });
  }

  function paneItemsById(): Record<PaneId, Array<{ item: LearningContentItem; expanded: boolean }>> {
    const byKey = new Map(currentContentItems().map((item) => [item.key, item]));
    function buildEntries(entries: PaneStackEntry[]): Array<{ item: LearningContentItem; expanded: boolean }> {
      return entries
        .map((entry) => {
          const item = byKey.get(entry.key);
          return item ? { item, expanded: entry.expanded } : null;
        })
        .filter((entry): entry is { item: LearningContentItem; expanded: boolean } => Boolean(entry));
    }

    const leftEntries = buildEntries(currentPaneStacks().left);
    const rightEntries = buildEntries(currentPaneStacks().right);
    const focus = workspaceSubmissionFocus();

    return {
      left: focus.left ? leftEntries.filter((entry) => entry.item.key === focus.left) : leftEntries,
      right: focus.right ? rightEntries.filter((entry) => entry.item.key === focus.right) : rightEntries
    };
  }

  function currentMaterialCount(): number {
    const module = currentActiveModule();
    if (module) {
      return module.materials.length;
    }
    return currentActiveModuleSummary()?.materials_count ?? 0;
  }

  function actionTaskId(): string | null {
    if (form && typeof form === "object" && "taskId" in form && typeof form.taskId === "string") {
      return form.taskId;
    }
    return null;
  }

  function currentModuleMeta(): string | null {
    const summary = currentActiveModuleSummary();
    if (!summary) {
      return null;
    }
    return `${summary.tasks_done}/${summary.tasks_total} Aufgaben · ${currentMaterialCount()} Materialien`;
  }

  function openModule(moduleId: string) {
    const module = graphModuleById(moduleId);
    if (!module || (module.status !== "open" && module.status !== "done")) {
      return;
    }

    const openTabs = modularWorkspace.openTabs.includes(moduleId)
      ? modularWorkspace.openTabs
      : [...modularWorkspace.openTabs, moduleId];

    setModularWorkspaceState({
      ...modularWorkspace,
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

    setModularWorkspaceState({
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

    setModularWorkspaceState({
      ...modularWorkspace,
      openTabs: remaining,
      activeTab: nextActive
    });
    syncModuleUrl(nextActive);
  }

  function switchView(view: WorkspaceViewMode) {
    setModularWorkspaceState({
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

  function restoreHistoryContext() {
    if (historyRestored || !data.historyTaskId) {
      return;
    }

    const itemKey = taskItemKey(data.historyTaskId);
    if (!currentContentItems().some((item) => item.key === itemKey)) {
      return;
    }

    historyRestored = true;
    setSubmissionWorkspace("left", itemKey);
    void scrollToItem("left", itemKey);
  }

  onMount(() => {
    const stored = readStoredWorkspaceState();

    if (data.activeModule) {
      moduleCache = {
        [data.activeModule.module.id]: plainModule(data.activeModule)
      };
    }

    if (isModularUnit()) {
      const seeded = seedModularWorkspaceState(stored.modular);
      setModularWorkspaceState(seeded);
      for (const moduleId of seeded.openTabs) {
        void ensureModuleLoaded(moduleId);
      }
    } else {
      setLinearWorkspaceState(stored.linear);
    }

    workspaceReady = true;
    restoreHistoryContext();
  });

  $effect(() => {
    if (!browser || !workspaceReady) {
      return;
    }

    const payload: StoredWorkspaceState = {
      version: 5,
      modular: modularWorkspace,
      linear: linearWorkspace
    };
    window.localStorage.setItem(storageKey(), JSON.stringify(payload));
  });

  $effect(() => {
    if (!isModularUnit() || !workspaceReady) {
      return;
    }

    void rebuildGraph();
  });

  $effect(() => {
    if (!isModularUnit() || !workspaceReady || !modularWorkspace.openTabs.length) {
      return;
    }

    for (const moduleId of modularWorkspace.openTabs) {
      void ensureModuleLoaded(moduleId);
    }
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }

    restoreHistoryContext();
  });

  $effect(() => {
    if (!workspaceReady || !actionTaskId()) {
      return;
    }

    const itemKey = taskItemKey(actionTaskId() as string);
    if (!currentContentItems().some((item) => item.key === itemKey)) {
      return;
    }

    setSubmissionWorkspace("left", itemKey);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }

    const available = new Set(currentContentItems().map((item) => item.key));
    const focus = workspaceSubmissionFocus();
    const leftInvalid = focus.left && !available.has(focus.left);
    const rightInvalid = focus.right && !available.has(focus.right);
    if (leftInvalid) {
      setSubmissionWorkspace("left", null);
    }
    if (rightInvalid) {
      setSubmissionWorkspace("right", null);
    }
  });
</script>

<svelte:head>
  <title>{data.selectedUnit?.unit.title ?? "Lernraum"} | GUSTAV</title>
</svelte:head>

<div class="workspace-page learning-unit-space">
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
      <LearningUnitOverview graph={data.graph} nodes={flowNodes} edges={flowEdges} />
    {:else}
      <section class="learning-unit-stage learning-unit-stage--content">
        {#if currentActiveModule()}
          <LearningUnitContentWorkspace
            titleLabel="Modul"
            title={openTabModules().length > 1 ? "Geöffnete Module" : currentActiveModule()?.module.title ?? "Modul"}
            meta={openTabModules().length > 1 ? `${openTabModules().length} Module geöffnet` : currentModuleMeta()}
            courseId={data.courseId}
            unitType="modular"
            moduleId={currentActiveModule()?.module.id ?? null}
            tocOpen={workspaceTocOpen()}
            splitView={workspaceSplitView()}
            activePane={workspaceActivePane()}
            visiblePaneIds={visiblePaneIds()}
            contentGroups={contentGroups()}
            paneItems={paneItemsById()}
            historyTaskId={data.historyTaskId}
            history={data.history}
            submittedTaskId={data.submittedTaskId}
            submissionErrorTaskId={actionTaskId()}
            submissionErrorMessage={form?.message ?? null}
            submissionFocusByPane={workspaceSubmissionFocus()}
            {itemDomId}
            onToggleToc={toggleToc}
            onToggleSplitView={() => setSplitView(!workspaceSplitView())}
            onSetActivePane={setActivePane}
            onOpenItem={openItemFromToc}
            onToggleItem={togglePaneItem}
            onEnterSubmissionWorkspace={(paneId, itemKey) => setSubmissionWorkspace(paneId, itemKey)}
            onExitSubmissionWorkspace={(paneId) => setSubmissionWorkspace(paneId, null)}
          />
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
      <LearningUnitContentWorkspace
        titleLabel="Lerneinheit"
        title={data.selectedUnit?.unit.title ?? "Lerneinheit"}
        meta={null}
        courseId={data.courseId}
        unitType="linear"
        moduleId={null}
        tocOpen={workspaceTocOpen()}
        splitView={workspaceSplitView()}
        activePane={workspaceActivePane()}
        visiblePaneIds={visiblePaneIds()}
        contentGroups={contentGroups()}
        paneItems={paneItemsById()}
        historyTaskId={data.historyTaskId}
        history={data.history}
        submittedTaskId={data.submittedTaskId}
        submissionErrorTaskId={actionTaskId()}
        submissionErrorMessage={form?.message ?? null}
        submissionFocusByPane={workspaceSubmissionFocus()}
        {itemDomId}
        onToggleToc={toggleToc}
        onToggleSplitView={() => setSplitView(!workspaceSplitView())}
        onSetActivePane={setActivePane}
        onOpenItem={openItemFromToc}
        onToggleItem={togglePaneItem}
        onEnterSubmissionWorkspace={(paneId, itemKey) => setSubmissionWorkspace(paneId, itemKey)}
        onExitSubmissionWorkspace={(paneId) => setSubmissionWorkspace(paneId, null)}
      />
    </section>
  {/if}
</div>
