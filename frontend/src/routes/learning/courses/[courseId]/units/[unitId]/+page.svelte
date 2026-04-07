<script lang="ts">
  import { applyAction } from "$app/forms";
  import { browser } from "$app/environment";
  import { onMount, tick } from "svelte";

  import ModeSwitch from "$lib/components/ui/ModeSwitch.svelte";
  import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";
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
  import { highlightedLearnerGraphModuleIds } from "$lib/learning-unit/graph-selection";
  import type { TeacherFlowEdge } from "$lib/graph/teacher-unit-flow";
  import type {
    LearningSubmission,
    LearningModuleContent,
    LearningUnitGraphModule
  } from "$lib/types/learning";
  import type { SubmitFunction } from "@sveltejs/kit";
  import type { ActionData, PageData } from "./$types";

  type WorkspaceViewMode = "overview" | "content";
  type ModularRestoreState = "idle" | "restoring" | "ready" | "failed";
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
  type LayoutPreferences = {
    tocWidth: number;
    workspaceWidth: number;
    splitRatio: number;
    tocGap: number;
    paneGap: number;
    fontScale: number;
  };
  type StoredWorkspaceState = {
    version: 11 | 12 | 13 | 14 | 15;
    modular?: Partial<ModularWorkspaceState>;
    linear?: Partial<LinearWorkspaceState>;
    layout?: Partial<LayoutPreferences>;
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
  let modularSettingsMenuOpen = $state(false);
  let layoutPreferences = $state<LayoutPreferences>(defaultLayoutPreferences());
  let workspaceRoot = $state<HTMLDivElement | null>(null);
  let historyTaskIdState = $state<string | null>(data.historyTaskId);
  let historyState = $state<LearningSubmission[]>(data.history);
  let submissionMessageState = $state<string | null>(data.message);
  let feedbackPendingTaskId = $state<string | null>(null);
  let feedbackStatusTaskId = $state<string | null>(null);
  let feedbackStatusMessage = $state<string | null>(null);
  let pendingSubmissionIntent = $state<"feedback" | "submit" | null>(null);
  let modularRestoreState = $state<ModularRestoreState>("idle");
  let modularRestoreMessage = $state<string | null>(null);
  let feedbackPollToken = 0;

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

  function currentViewportWidth(): number {
    return browser ? window.innerWidth : 1280;
  }

  function viewportLayoutBucket(viewportWidth: number): "compact" | "medium" | "wide" | "xwide" {
    if (viewportWidth < 760) {
      return "compact";
    }
    if (viewportWidth < 1180) {
      return "medium";
    }
    if (viewportWidth < 1500) {
      return "wide";
    }
    return "xwide";
  }

  function viewportWorkspaceWidth(viewportWidth: number, preferredRem: number): number {
    const viewportBasedRem = (viewportWidth - 48) / 16;
    return clamp(Math.floor(Math.min(preferredRem, viewportBasedRem) * 2) / 2, 16, 320);
  }

  function defaultWorkspaceChrome(viewportWidth = currentViewportWidth()): Pick<ModularWorkspaceState, "splitView" | "tocOpen" | "activePane"> {
    const bucket = viewportLayoutBucket(viewportWidth);
    if (bucket === "compact") {
      return { splitView: false, tocOpen: false, activePane: "left" };
    }
    if (bucket === "medium") {
      return { splitView: false, tocOpen: false, activePane: "left" };
    }
    return { splitView: false, tocOpen: true, activePane: "left" };
  }

  function defaultModularWorkspaceState(viewportWidth = currentViewportWidth()): ModularWorkspaceState {
    const chromeDefaults = defaultWorkspaceChrome(viewportWidth);
    return {
      view: "overview",
      openTabs: [],
      activeTab: null,
      splitView: chromeDefaults.splitView,
      tocOpen: chromeDefaults.tocOpen,
      activePane: chromeDefaults.activePane,
      paneStacks: null,
      submissionFocus: defaultSubmissionFocus()
    };
  }

  function defaultLinearWorkspaceState(viewportWidth = currentViewportWidth()): LinearWorkspaceState {
    const chromeDefaults = defaultWorkspaceChrome(viewportWidth);
    return {
      splitView: chromeDefaults.splitView,
      tocOpen: chromeDefaults.tocOpen,
      activePane: chromeDefaults.activePane,
      paneStacks: null,
      submissionFocus: defaultSubmissionFocus()
  };
  }

  function defaultLayoutPreferences(viewportWidth = currentViewportWidth()): LayoutPreferences {
    const bucket = viewportLayoutBucket(viewportWidth);
    if (bucket === "compact") {
      return {
        tocWidth: 14.5,
        workspaceWidth: viewportWorkspaceWidth(viewportWidth, 42),
        splitRatio: 50,
        tocGap: 0.75,
        paneGap: 0.75,
        fontScale: 1
      };
    }
    if (bucket === "medium") {
      return {
        tocWidth: 15,
        workspaceWidth: viewportWorkspaceWidth(viewportWidth, 64),
        splitRatio: 50,
        tocGap: 0.9,
        paneGap: 0.9,
        fontScale: 1
      };
    }
    if (bucket === "wide") {
      return {
        tocWidth: 16.25,
        workspaceWidth: viewportWorkspaceWidth(viewportWidth, 64),
        splitRatio: 50,
        tocGap: 1.1,
        paneGap: 1.1,
        fontScale: 1
      };
    }
    return {
      tocWidth: 17,
      workspaceWidth: viewportWorkspaceWidth(viewportWidth, 64),
      splitRatio: 50,
      tocGap: 1.25,
      paneGap: 1.25,
      fontScale: 1
    };
  }

  function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
  }

  function normalizeLayoutPreferences(raw: unknown, viewportWidth = currentViewportWidth()): LayoutPreferences {
    const candidate = raw && typeof raw === "object" ? (raw as Partial<LayoutPreferences>) : {};
    const defaults = defaultLayoutPreferences(viewportWidth);
    return {
      tocWidth: typeof candidate.tocWidth === "number" ? clamp(candidate.tocWidth, 0, 120) : defaults.tocWidth,
      workspaceWidth:
        typeof candidate.workspaceWidth === "number"
          ? clamp(candidate.workspaceWidth, 16, 320)
          : typeof (candidate as { singlePaneWidth?: unknown }).singlePaneWidth === "number"
            ? clamp(Number((candidate as { singlePaneWidth?: unknown }).singlePaneWidth) + 18, 16, 320)
            : defaults.workspaceWidth,
      splitRatio:
        typeof candidate.splitRatio === "number" ? clamp(candidate.splitRatio, 0, 100) : defaults.splitRatio,
      tocGap:
        typeof candidate.tocGap === "number" ? clamp(candidate.tocGap, 0, 40) : defaults.tocGap,
      paneGap:
        typeof candidate.paneGap === "number" ? clamp(candidate.paneGap, 0, 40) : defaults.paneGap,
      fontScale:
        typeof candidate.fontScale === "number" ? clamp(candidate.fontScale, 0.1, 4) : defaults.fontScale
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

  function readStoredWorkspaceState(viewportWidth = currentViewportWidth()): {
    modular: ModularWorkspaceState;
    linear: LinearWorkspaceState;
    layout: LayoutPreferences;
  } {
    if (!browser) {
      return {
        modular: defaultModularWorkspaceState(viewportWidth),
        linear: defaultLinearWorkspaceState(viewportWidth),
        layout: defaultLayoutPreferences(viewportWidth)
      };
    }

    try {
      const raw = window.localStorage.getItem(storageKey());
      if (!raw) {
        return {
          modular: defaultModularWorkspaceState(viewportWidth),
          linear: defaultLinearWorkspaceState(viewportWidth),
          layout: defaultLayoutPreferences(viewportWidth)
        };
      }

      const parsed = JSON.parse(raw) as StoredWorkspaceState | Partial<ModularWorkspaceState>;
      if (
        parsed &&
        typeof parsed === "object" &&
        "version" in parsed &&
        (parsed.version === 11 || parsed.version === 12 || parsed.version === 13 || parsed.version === 14 || parsed.version === 15) &&
        ("modular" in parsed || "linear" in parsed)
      ) {
        return {
          modular: normalizeModularWorkspaceState(parsed.modular ?? null),
          linear: normalizeLinearWorkspaceState(parsed.linear ?? null),
          layout: normalizeLayoutPreferences(parsed.layout ?? null, viewportWidth)
        };
      }

      return {
        modular: normalizeModularWorkspaceState(parsed),
        linear: defaultLinearWorkspaceState(viewportWidth),
        layout: defaultLayoutPreferences(viewportWidth)
      };
    } catch {
      return {
        modular: defaultModularWorkspaceState(viewportWidth),
        linear: defaultLinearWorkspaceState(viewportWidth),
        layout: defaultLayoutPreferences(viewportWidth)
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

  function delay(ms: number): Promise<void> {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  async function fetchModuleContent(moduleId: string): Promise<LearningModuleContent> {
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

    return (await response.json()) as LearningModuleContent;
  }

  async function ensureModuleLoaded(moduleId: string) {
    if (!browser || moduleCache[moduleId] || moduleLoading[moduleId]) {
      return Boolean(moduleCache[moduleId]);
    }

    moduleLoading = { ...moduleLoading, [moduleId]: true };
    moduleErrors = { ...moduleErrors, [moduleId]: null };

    try {
      const payload = await fetchModuleContent(moduleId);
      moduleCache = {
        ...moduleCache,
        [moduleId]: plainModule(payload)
      };
      return true;
    } catch {
      moduleErrors = {
        ...moduleErrors,
        [moduleId]: "Das Modul konnte nicht geladen werden."
      };
      return false;
    } finally {
      moduleLoading = {
        ...moduleLoading,
        [moduleId]: false
      };
    }
  }

  async function restoreOpenModules(moduleIds: string[]) {
    if (!browser || !isModularUnit()) {
      return;
    }

    const pendingIds = moduleIds.filter((moduleId) => !moduleCache[moduleId]);
    if (!pendingIds.length) {
      modularRestoreState = "ready";
      modularRestoreMessage = null;
      restoreHistoryContext();
      return;
    }

    modularRestoreState = "restoring";
    modularRestoreMessage = null;

    const restorePromise = Promise.all(pendingIds.map((moduleId) => ensureModuleLoaded(moduleId))).then((results) =>
      results.every(Boolean)
    );
    const timeoutPromise = delay(8000).then(() => false);
    const restoreSucceeded = await Promise.race([restorePromise, timeoutPromise]);

    if (restoreSucceeded) {
      modularRestoreState = "ready";
      modularRestoreMessage = null;
      restoreHistoryContext();
      return;
    }

    modularRestoreState = "failed";
    modularRestoreMessage = "Die Inhalte konnten nicht wiederhergestellt werden. Bitte öffne die Module erneut.";
    historyRestored = false;
    setModularWorkspaceState({
      ...modularWorkspace,
      view: "overview",
      submissionFocus: defaultSubmissionFocus()
    });
    syncModuleUrl(null);
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
          left: paneId === "left" ? { itemKey, mode } : { itemKey: null, mode: null },
          right: paneId === "right" ? { itemKey, mode } : { itemKey: null, mode: null }
        }
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      submissionFocus: {
        left: paneId === "left" ? { itemKey, mode } : { itemKey: null, mode: null },
        right: paneId === "right" ? { itemKey, mode } : { itemKey: null, mode: null }
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

    return {
      left: buildEntries(currentPaneStacks().left),
      right: buildEntries(currentPaneStacks().right)
    };
  }

  function actionTaskId(): string | null {
    if (form && typeof form === "object" && "taskId" in form && typeof form.taskId === "string") {
      return form.taskId;
    }
    return null;
  }

  function clearSubmissionWorkspace() {
    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        submissionFocus: defaultSubmissionFocus()
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      submissionFocus: defaultSubmissionFocus()
    });
  }

  async function loadSubmissionHistory(taskId: string): Promise<LearningSubmission[]> {
    const response = await fetch(
      `/api/learning/courses/${encodeURIComponent(data.courseId)}/tasks/${encodeURIComponent(taskId)}/submissions?limit=10&offset=0`,
      {
        credentials: "include",
        cache: "no-store"
      }
    );
    if (!response.ok) {
      throw new Error(`history_failed_${response.status}`);
    }
    return (await response.json()) as LearningSubmission[];
  }

  async function pollFeedbackSubmission(
    taskId: string,
    submissionId: string | null,
    intent: "feedback" | "submit"
  ) {
    const pollToken = ++feedbackPollToken;
    const fastPollAttempts = 30;
    historyTaskIdState = taskId;
    submissionMessageState = null;
    feedbackPendingTaskId = taskId;
    feedbackStatusTaskId = taskId;
    pendingSubmissionIntent = intent;
    feedbackStatusMessage = intent === "submit" ? "Abgabe wird verarbeitet ..." : "Rückmeldung wird erstellt ...";

    for (let attempt = 0; ; attempt += 1) {
      try {
        const entries = await loadSubmissionHistory(taskId);
        const matchingSubmission = submissionId
          ? entries.find((entry) => entry.id === submissionId) ?? null
          : entries.find((entry) => entry.intent === "feedback") ?? null;

        if (pollToken !== feedbackPollToken) {
          return;
        }

        if (matchingSubmission?.analysis_status === "completed") {
          historyState = entries;
          submissionMessageState = intent === "submit" ? "submitted" : "feedback";
          feedbackPendingTaskId = null;
          feedbackStatusTaskId = null;
          feedbackStatusMessage = null;
          pendingSubmissionIntent = null;
          return;
        }

        if (matchingSubmission?.analysis_status === "failed") {
          historyState = entries;
          feedbackPendingTaskId = null;
          feedbackStatusTaskId = taskId;
          pendingSubmissionIntent = null;
          feedbackStatusMessage =
            intent === "submit"
              ? "Die Auswertung konnte nicht erstellt werden."
              : "Die Rückmeldung konnte nicht erstellt werden.";
          return;
        }
      } catch {
        if (pollToken !== feedbackPollToken) {
          return;
        }
      }

      if (attempt >= fastPollAttempts && feedbackStatusTaskId === taskId) {
        feedbackStatusMessage =
          intent === "submit"
            ? "Die Auswertung dauert länger als üblich ..."
            : "Die Rückmeldung dauert länger als üblich ...";
      }

      await delay(attempt >= fastPollAttempts ? 5000 : 2000);
    }
  }

  function enhanceTaskForm(taskId: string): SubmitFunction {
    return ({ submitter }) => {
      if (!(submitter instanceof HTMLButtonElement)) {
        return;
      }

      const intent = submitter.value === "feedback" ? "feedback" : "submit";

      feedbackPendingTaskId = taskId;
      feedbackStatusTaskId = taskId;
      pendingSubmissionIntent = intent;
      feedbackStatusMessage = intent === "submit" ? "Abgabe wird verarbeitet ..." : "Rückmeldung wird erstellt ...";

      return async ({ result }) => {
        if (result.type === "success") {
          const payload = (result.data ?? {}) as {
            feedbackRequestedTaskId?: string;
            feedbackSubmissionId?: string | null;
            pendingIntent?: "feedback" | "submit";
          };
          if ((payload.pendingIntent ?? intent) === "submit") {
            clearSubmissionWorkspace();
          }
          await pollFeedbackSubmission(
            payload.feedbackRequestedTaskId ?? taskId,
            payload.feedbackSubmissionId ?? null,
            payload.pendingIntent ?? intent
          );
          return;
        }

        feedbackPendingTaskId = null;
        pendingSubmissionIntent = null;

        if (result.type === "failure") {
          const payload = (result.data ?? {}) as { message?: string };
          feedbackStatusTaskId = taskId;
          feedbackStatusMessage =
            payload.message ??
            (intent === "submit"
              ? "Die Abgabe konnte nicht verarbeitet werden."
              : "Die Rückmeldung konnte nicht angefordert werden.");
          return;
        }

        await applyAction(result);
      };
    };
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
    modularRestoreState = "ready";
    modularRestoreMessage = null;
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

  function updateLayoutPreferences(next: Partial<LayoutPreferences>) {
    layoutPreferences = {
      ...layoutPreferences,
      ...next
    };
  }

  function applyWorkspaceWidth(value: number) {
    workspaceRoot?.style.setProperty("--learning-unit-workspace-width", `${value}rem`);
  }

  function applyFontScale(value: number) {
    workspaceRoot?.style.setProperty("--learning-unit-font-scale", String(value));
  }

  function previewWorkspaceWidth(value: number) {
    applyWorkspaceWidth(clamp(value, 16, 320));
  }

  function commitWorkspaceWidth(value: number) {
    const nextWidth = clamp(value, 16, 320);
    applyWorkspaceWidth(nextWidth);
    updateLayoutPreferences({ workspaceWidth: nextWidth });
  }

  function previewFontScale(value: number) {
    applyFontScale(clamp(value, 0.1, 4));
  }

  function commitFontScale(value: number) {
    const nextScale = clamp(value, 0.1, 4);
    applyFontScale(nextScale);
    updateLayoutPreferences({ fontScale: nextScale });
  }

  function resetLayoutPreferences() {
    const viewportWidth = currentViewportWidth();
    const layoutDefaults = defaultLayoutPreferences(viewportWidth);
    const chromeDefaults = defaultWorkspaceChrome(viewportWidth);

    layoutPreferences = layoutDefaults;
    applyWorkspaceWidth(layoutDefaults.workspaceWidth);
    applyFontScale(layoutDefaults.fontScale);

    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        splitView: chromeDefaults.splitView,
        tocOpen: chromeDefaults.tocOpen,
        activePane: chromeDefaults.activePane
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      splitView: chromeDefaults.splitView,
      tocOpen: chromeDefaults.tocOpen,
      activePane: chromeDefaults.activePane
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
        highlightedLearnerGraphModuleIds(modularWorkspace.openTabs),
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
    const viewportWidth = currentViewportWidth();
    const stored = readStoredWorkspaceState(viewportWidth);

    if (data.activeModule) {
      moduleCache = {
        [data.activeModule.module.id]: plainModule(data.activeModule)
      };
    }

    if (isModularUnit()) {
      const seeded = seedModularWorkspaceState(stored.modular);
      setModularWorkspaceState(seeded);
      layoutPreferences = stored.layout;
      if (seeded.view === "content" && seeded.openTabs.length > 0) {
        void restoreOpenModules(seeded.openTabs);
      } else {
        modularRestoreState = "idle";
      }
    } else {
      setLinearWorkspaceState(stored.linear);
      layoutPreferences = stored.layout;
    }

    applyWorkspaceWidth(stored.layout.workspaceWidth);
    applyFontScale(stored.layout.fontScale);
    workspaceReady = true;
    if (!isModularUnit()) {
      restoreHistoryContext();
    }
  });

  $effect(() => {
    historyTaskIdState = data.historyTaskId;
    historyState = data.history;
    submissionMessageState = data.message;
  });

  $effect(() => {
    if (!browser || !workspaceReady) {
      return;
    }

    const payload: StoredWorkspaceState = {
      version: 15,
      modular: modularWorkspace,
      linear: linearWorkspace,
      layout: layoutPreferences
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
    if (!workspaceReady) {
      return;
    }

    if (!isModularUnit() || modularRestoreState === "ready") {
      restoreHistoryContext();
    }
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

<div bind:this={workspaceRoot} class="workspace-page learning-unit-space">
  {#if data.message === "submitted"}
    <p class="flash flash-success learning-unit-flash">Abgabe gespeichert.</p>
  {/if}

  {#if modularRestoreMessage}
    <p class="flash flash-error learning-unit-flash">{modularRestoreMessage}</p>
  {/if}

  {#if form?.message}
    <p class="flash flash-error learning-unit-flash">{form.message}</p>
  {/if}

  {#if isModularUnit()}
    <section class="learning-unit-toolbar">
      <div class="learning-unit-toolbar__main">
        <div class="learning-unit-toolbar__leading">
          <ModeSwitch
            label="Lerneinheit"
            options={[
              {
                label: "Übersicht",
                current: modularWorkspace.view === "overview",
                onSelect: () => switchView("overview")
              },
              {
                label: "Inhalte",
                current: modularWorkspace.view === "content",
                onSelect: () => switchView("content")
              }
            ]}
          />
        </div>

        {#if modularWorkspace.view === "content"}
          <div class="learning-unit-toolbar__utility">
            <WorkspaceSettingsMenu
              open={modularSettingsMenuOpen}
              tocOpen={workspaceTocOpen()}
              splitView={workspaceSplitView()}
              showSplitToggle={true}
              tocWidth={layoutPreferences.tocWidth}
              workspaceWidth={layoutPreferences.workspaceWidth}
              splitRatio={layoutPreferences.splitRatio}
              tocGap={layoutPreferences.tocGap}
              paneGap={layoutPreferences.paneGap}
              fontScale={layoutPreferences.fontScale}
              onToggleMenu={() => {
                modularSettingsMenuOpen = !modularSettingsMenuOpen;
              }}
              onToggleToc={toggleToc}
              onToggleSplitView={() => setSplitView(!workspaceSplitView())}
              onResetLayout={resetLayoutPreferences}
              onUpdateTocWidth={(value) => updateLayoutPreferences({ tocWidth: value })}
              onPreviewWorkspaceWidth={previewWorkspaceWidth}
              onCommitWorkspaceWidth={commitWorkspaceWidth}
              onPreviewFontScale={previewFontScale}
              onCommitFontScale={commitFontScale}
              onUpdateSplitRatio={(value) => updateLayoutPreferences({ splitRatio: value })}
              onUpdateTocGap={(value) => updateLayoutPreferences({ tocGap: value })}
              onUpdatePaneGap={(value) => updateLayoutPreferences({ paneGap: value })}
            />
          </div>
        {/if}
      </div>
    </section>

    {#if modularWorkspace.view === "overview"}
      <LearningUnitOverview graph={data.graph} nodes={flowNodes} edges={flowEdges} />
    {:else}
      <div class="learning-unit-layout-rail">
        <div class="learning-unit-layout-frame">
          <section class="learning-unit-stage learning-unit-stage--content">
            {#if modularRestoreState === "restoring"}
              <section class="workspace-panel learning-unit-empty-state">
                <p class="learning-unit-empty-copy">Inhalte werden wiederhergestellt …</p>
              </section>
            {:else if modularRestoreState === "failed"}
              <section class="workspace-panel learning-unit-empty-state">
                <p class="learning-unit-empty-copy">Der Lernraum wechselt zurück in die Übersicht.</p>
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
                historyTaskId={historyTaskIdState}
                history={historyState}
                submittedTaskId={data.submittedTaskId}
                submissionMessage={submissionMessageState}
                submissionErrorTaskId={actionTaskId()}
                submissionErrorMessage={form?.message ?? null}
                {feedbackPendingTaskId}
                {feedbackStatusTaskId}
                {feedbackStatusMessage}
                {pendingSubmissionIntent}
                submissionFocusByPane={workspaceSubmissionFocus()}
                submissionModeByPane={workspaceSubmissionModes()}
                {enhanceTaskForm}
                showSplitToggle={false}
                layoutMenuEnabled={false}
                tocWidth={layoutPreferences.tocWidth}
                workspaceWidth={layoutPreferences.workspaceWidth}
                splitRatio={layoutPreferences.splitRatio}
                tocGap={layoutPreferences.tocGap}
                paneGap={layoutPreferences.paneGap}
                fontScale={layoutPreferences.fontScale}
                {itemDomId}
                onToggleToc={toggleToc}
                onToggleSplitView={() => setSplitView(!workspaceSplitView())}
                onResetLayout={resetLayoutPreferences}
                onUpdateTocWidth={(value) => updateLayoutPreferences({ tocWidth: value })}
                onPreviewWorkspaceWidth={previewWorkspaceWidth}
                onCommitWorkspaceWidth={commitWorkspaceWidth}
                onPreviewFontScale={previewFontScale}
                onCommitFontScale={commitFontScale}
                onUpdateSplitRatio={(value) => updateLayoutPreferences({ splitRatio: value })}
                onUpdateTocGap={(value) => updateLayoutPreferences({ tocGap: value })}
                onUpdatePaneGap={(value) => updateLayoutPreferences({ paneGap: value })}
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
        </div>
      </div>
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
        historyTaskId={historyTaskIdState}
        history={historyState}
        submittedTaskId={data.submittedTaskId}
        submissionMessage={submissionMessageState}
        submissionErrorTaskId={actionTaskId()}
        submissionErrorMessage={form?.message ?? null}
        {feedbackPendingTaskId}
        {feedbackStatusTaskId}
        {feedbackStatusMessage}
        {pendingSubmissionIntent}
        submissionFocusByPane={workspaceSubmissionFocus()}
        submissionModeByPane={workspaceSubmissionModes()}
        {enhanceTaskForm}
        showSplitToggle={true}
        layoutMenuEnabled={true}
        tocWidth={layoutPreferences.tocWidth}
        workspaceWidth={layoutPreferences.workspaceWidth}
        splitRatio={layoutPreferences.splitRatio}
        tocGap={layoutPreferences.tocGap}
        paneGap={layoutPreferences.paneGap}
        fontScale={layoutPreferences.fontScale}
        {itemDomId}
        onToggleToc={toggleToc}
        onToggleSplitView={() => setSplitView(!workspaceSplitView())}
        onResetLayout={resetLayoutPreferences}
        onUpdateTocWidth={(value) => updateLayoutPreferences({ tocWidth: value })}
        onPreviewWorkspaceWidth={previewWorkspaceWidth}
        onCommitWorkspaceWidth={commitWorkspaceWidth}
        onPreviewFontScale={previewFontScale}
        onCommitFontScale={commitFontScale}
        onUpdateSplitRatio={(value) => updateLayoutPreferences({ splitRatio: value })}
        onUpdateTocGap={(value) => updateLayoutPreferences({ tocGap: value })}
        onUpdatePaneGap={(value) => updateLayoutPreferences({ paneGap: value })}
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
