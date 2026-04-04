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
  type SubmissionFocusState = {
    itemKey: string | null;
    mode: "text" | "upload" | null;
  };
  type ModularWorkspaceState = {
    view: WorkspaceViewMode;
    openTabs: string[];
    activeTab: string | null;
    splitView: boolean;
    tocOpen: boolean;
    activePane: PaneId;
    paneStacks: PaneStacks | null;
    submissionFocus: Record<PaneId, SubmissionFocusState>;
  };
  type LinearWorkspaceState = {
    splitView: boolean;
    tocOpen: boolean;
    activePane: PaneId;
    paneStacks: PaneStacks | null;
    submissionFocus: Record<PaneId, SubmissionFocusState>;
  };
  type StoredWorkspaceState = {
    version: 7;
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

  function defaultSubmissionFocus(): Record<PaneId, SubmissionFocusState> {
    return {
      left: { itemKey: null, mode: null },
      right: { itemKey: null, mode: null }
    };
  }

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
      submissionFocus: defaultSubmissionFocus()
    };
  }

  function defaultLinearWorkspaceState(): LinearWorkspaceState {
    return {
      splitView: false,
      tocOpen: true,
      activePane: "left",
      paneStacks: null,
      submissionFocus: defaultSubmissionFocus()
  };
  }

  function normalizeSubmissionFocus(raw: unknown): Record<PaneId, SubmissionFocusState> {
    const candidate = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};

    function paneState(value: unknown): SubmissionFocusState {
      if (value && typeof value === "object") {
        const pane = value as { itemKey?: unknown; mode?: unknown };
        return {
          itemKey: typeof pane.itemKey === "string" ? pane.itemKey : null,
          mode: pane.mode === "text" || pane.mode === "upload" ? pane.mode : null
        };
      }
      if (typeof value === "string") {
        return { itemKey: value, mode: null };
      }
      return { itemKey: null, mode: null };
    }

    return {
      left: paneState(candidate.left),
      right: paneState(candidate.right)
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
      tocOpen:
        typeof candidate.tocOpen === "boolean"
          ? candidate.tocOpen
          : candidate.splitView === true
            ? false
            : true,
      activePane: candidate.activePane === "right" ? "right" : "left",
      paneStacks: normalizePaneStacks(candidate.paneStacks),
      submissionFocus: normalizeSubmissionFocus(candidate.submissionFocus)
    };
  }

  function normalizeLinearWorkspaceState(raw: unknown): LinearWorkspaceState {
    const candidate = raw && typeof raw === "object" ? (raw as Partial<LinearWorkspaceState>) : {};
    return {
      splitView: Boolean(candidate.splitView),
      tocOpen:
        typeof candidate.tocOpen === "boolean"
          ? candidate.tocOpen
          : candidate.splitView === true
            ? false
            : true,
      activePane: candidate.activePane === "right" ? "right" : "left",
      paneStacks: normalizePaneStacks(candidate.paneStacks),
      submissionFocus: normalizeSubmissionFocus(candidate.submissionFocus)
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
        parsed.version === 7 &&
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

  function orderedOpenModulesForContent(): LearningUnitGraphModule[] {
    return orderedOpenModules(data.graph, modularWorkspace.openTabs);
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
    const focus = isModularUnit() ? modularWorkspace.submissionFocus : linearWorkspace.submissionFocus;
    return {
      left: focus.left.itemKey,
      right: focus.right.itemKey
    };
  }

  function submissionFocusState(): Record<PaneId, SubmissionFocusState> {
    return isModularUnit() ? modularWorkspace.submissionFocus : linearWorkspace.submissionFocus;
  }

  function workspaceSubmissionModes(): Record<PaneId, "text" | "upload" | null> {
    const focus = submissionFocusState();
    return {
      left: focus.left.mode,
      right: focus.right.mode
    };
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
          : { left: modularWorkspace.submissionFocus.left, right: { itemKey: null, mode: null } }
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
        : { left: linearWorkspace.submissionFocus.left, right: { itemKey: null, mode: null } }
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
    setSubmissionWorkspace(targetPane, null, null);
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

  function setSubmissionWorkspace(paneId: PaneId, itemKey: string | null, mode: "text" | "upload" | null = null) {
    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        submissionFocus: {
          ...modularWorkspace.submissionFocus,
          [paneId]: { itemKey, mode }
        }
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      submissionFocus: {
        ...linearWorkspace.submissionFocus,
        [paneId]: { itemKey, mode }
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
    const focus = submissionFocusState();

    return {
      left: focus.left.itemKey ? leftEntries.filter((entry) => entry.item.key === focus.left.itemKey) : leftEntries,
      right: focus.right.itemKey ? rightEntries.filter((entry) => entry.item.key === focus.right.itemKey) : rightEntries
    };
  }

  function actionTaskId(): string | null {
    if (form && typeof form === "object" && "taskId" in form && typeof form.taskId === "string") {
      return form.taskId;
    }
    return null;
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

  function removeOpenModule(moduleId: string) {
    const currentIndex = modularWorkspace.openTabs.indexOf(moduleId);
    if (currentIndex < 0) {
      return;
    }

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
    setSubmissionWorkspace("left", itemKey, data.submissionMode);
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
      version: 7,
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

    setSubmissionWorkspace("left", itemKey, null);
  });

  $effect(() => {
    if (!workspaceReady) {
      return;
    }

    const available = new Set(currentContentItems().map((item) => item.key));
    const focus = submissionFocusState();
    const leftInvalid = focus.left.itemKey && !available.has(focus.left.itemKey);
    const rightInvalid = focus.right.itemKey && !available.has(focus.right.itemKey);
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
    <section class="learning-unit-toolbar">
      <div class="learning-unit-toolbar__main">
        <div class="learning-unit-toolbar__leading">
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
        </div>

        {#if modularWorkspace.view === "content"}
          <div class="learning-unit-toolbar__utility">
            <button
              aria-label={workspaceTocOpen() ? "Inhaltsverzeichnis ausblenden" : "Inhaltsverzeichnis einblenden"}
              class:workspace-top-action--active={workspaceTocOpen()}
              class="workspace-top-action workspace-top-action--quiet learning-unit-view-toggle"
              title={workspaceTocOpen() ? "Inhaltsverzeichnis ausblenden" : "Inhaltsverzeichnis einblenden"}
              type="button"
              onclick={toggleToc}
            >
              <svg aria-hidden="true" class="learning-unit-view-toggle__icon" viewBox="0 0 20 20">
                <rect x="3" y="4" width="4" height="12" rx="0.9"></rect>
                <path d="M10 6.5h7"></path>
                <path d="M10 10h7"></path>
                <path d="M10 13.5h7"></path>
              </svg>
            </button>
            <button
              aria-label={workspaceSplitView() ? "Eine Ansicht" : "Zwei Ansichten"}
              class:workspace-top-action--active={workspaceSplitView()}
              class="workspace-top-action workspace-top-action--quiet learning-unit-view-toggle"
              title={workspaceSplitView() ? "Eine Ansicht" : "Zwei Ansichten"}
              type="button"
              onclick={() => setSplitView(!workspaceSplitView())}
            >
              <svg aria-hidden="true" class="learning-unit-view-toggle__icon" viewBox="0 0 20 20">
                {#if workspaceSplitView()}
                  <rect x="2.5" y="4" width="5.5" height="12" rx="1.2"></rect>
                  <rect x="12" y="4" width="5.5" height="12" rx="1.2"></rect>
                {:else}
                  <rect x="3" y="4" width="14" height="12" rx="1.4"></rect>
                {/if}
              </svg>
            </button>
          </div>
        {/if}
      </div>
    </section>

    {#if modularWorkspace.view === "overview"}
      <LearningUnitOverview graph={data.graph} nodes={flowNodes} edges={flowEdges} />
    {:else}
      <section class="learning-unit-stage learning-unit-stage--content">
        {#if modularWorkspace.activeTab && moduleLoading[modularWorkspace.activeTab]}
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
          <LearningUnitContentWorkspace
            titleLabel=""
            title=""
            meta={null}
            courseId={data.courseId}
            unitType="modular"
            moduleId={modularWorkspace.activeTab}
            tocOpen={workspaceTocOpen()}
            splitView={workspaceSplitView()}
            activePane={workspaceActivePane()}
            visiblePaneIds={visiblePaneIds()}
            contentGroups={contentGroups()}
            paneItems={paneItemsById()}
            historyTaskId={data.historyTaskId}
            history={data.history}
            submittedTaskId={data.submittedTaskId}
            submissionMessage={data.message}
            submissionErrorTaskId={actionTaskId()}
            submissionErrorMessage={form?.message ?? null}
            submissionFocusByPane={workspaceSubmissionFocus()}
            submissionModeByPane={workspaceSubmissionModes()}
            showSplitToggle={false}
            {itemDomId}
            onToggleToc={toggleToc}
            onToggleSplitView={() => setSplitView(!workspaceSplitView())}
            onSetActivePane={setActivePane}
            onOpenItem={openItemFromToc}
            onRemoveGroup={removeOpenModule}
            onToggleItem={togglePaneItem}
            onEnterSubmissionWorkspace={(paneId, itemKey, mode) => setSubmissionWorkspace(paneId, itemKey, mode ?? "text")}
            onEnterUploadWorkspace={(paneId, itemKey) => setSubmissionWorkspace(paneId, itemKey, "upload")}
            onExitSubmissionWorkspace={(paneId) => setSubmissionWorkspace(paneId, null)}
          />
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
        submissionMessage={data.message}
        submissionErrorTaskId={actionTaskId()}
        submissionErrorMessage={form?.message ?? null}
        submissionFocusByPane={workspaceSubmissionFocus()}
        submissionModeByPane={workspaceSubmissionModes()}
        showSplitToggle={true}
        {itemDomId}
        onToggleToc={toggleToc}
        onToggleSplitView={() => setSplitView(!workspaceSplitView())}
        onSetActivePane={setActivePane}
        onOpenItem={openItemFromToc}
        onToggleItem={togglePaneItem}
        onEnterSubmissionWorkspace={(paneId, itemKey, mode) => setSubmissionWorkspace(paneId, itemKey, mode ?? "text")}
        onEnterUploadWorkspace={(paneId, itemKey) => setSubmissionWorkspace(paneId, itemKey, "upload")}
        onExitSubmissionWorkspace={(paneId) => setSubmissionWorkspace(paneId, null)}
      />
    </section>
  {/if}
</div>
