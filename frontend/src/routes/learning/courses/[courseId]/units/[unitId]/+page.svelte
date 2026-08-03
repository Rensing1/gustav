<script lang="ts">
  import { applyAction } from "$app/forms";
  import { browser } from "$app/environment";
  import { onMount, tick } from "svelte";

  import ModeSwitch from "$lib/components/ui/ModeSwitch.svelte";
  import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";
  import LearnerContentWorkspace from "$lib/components/learning-unit/LearnerContentWorkspace.svelte";
  import LearningUnitOverview from "$lib/components/learning-unit/LearningUnitOverview.svelte";
  import {
    buildLearningUnitFlow,
    type LearningFlowNode
  } from "$lib/graph/learning-unit-flow";
  import { handleBrowserAuthRecovery } from "$lib/utils/browser-auth-recovery";
  import { prepareBrowserStorageUpload } from "$lib/utils/browser-storage-upload";
  import {
    FILIUS_FLS_MIME,
    MAKECODE_HEX_MIME,
    PDF_MIME,
    SCRATCH_SB3_MIME
  } from "$lib/utils/submission-mime-types";
  import { buildLearningSubmissionHistoryUrl, MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE } from "$lib/utils/learning-submission-history-url";
  import { learningSubmissionFailureMessage } from "$lib/utils/learning-failures";
  import {
    contentGroupsForModules,
    contentGroupsForSections,
    emptyReviewFocus,
    emptySubmissionFocus,
    flattenContentGroups,
    moduleContentItems,
    type LearningUnitViewState,
    type ModularWorkspaceSnapshot,
    orderedOpenModules,
    reconcileModularWorkspaceState,
    reconcilePaneStacks,
    reopenMaterialEntries,
    setPaneReviewFocus,
    setPaneSubmissionFocus,
    togglePaneReviewFocus,
    togglePaneSubmissionFocus,
    type ContentGroup,
    type LearningContentItem,
    type PaneId,
    type PaneStackEntry,
    type PaneStacks,
    type ReviewFocusByPane,
    type SubmissionFocusState
  } from "$lib/learning-unit/workspace";
  import {
    clamp,
    defaultLayoutPreferences,
    defaultLinearWorkspaceState,
    defaultModularWorkspaceState,
    defaultWorkspaceChrome,
    normalizeLayoutPreferences,
    normalizeLinearWorkspaceState,
    normalizeModularWorkspaceState,
    type LayoutPreferences,
    type LinearWorkspaceState,
    type ModularWorkspaceState
  } from "$lib/learning-unit/layout";
  import {
    learningUnitWorkspaceStorageKey,
    readLearningUnitWorkspaceState,
    serializeLearningUnitWorkspaceState
  } from "$lib/learning-unit/workspace-storage";
  import {
    defaultLearnerWorkspaceState,
    learnerWorkspaceStorageKeys,
    readLearnerWorkspaceState,
    serializeLearnerWorkspacePersistentState,
    serializeLearnerWorkspaceTabState,
    type LearnerContextReference,
    type LearnerWorkspaceState
  } from "$lib/learning-unit/learner-workspace-state";
  import { highlightedLearnerGraphModuleIds } from "$lib/learning-unit/graph-selection";
  import type { TeacherFlowEdge } from "$lib/graph/teacher-unit-flow";
  import type {
    LearningSubmission,
    LearningModuleContent,
    LearningTask,
    LearningUnitGraph,
    LearningUnitGraphModule
  } from "$lib/types/learning";
  import type { SubmitFunction } from "@sveltejs/kit";
  import type { ActionData, PageData } from "./$types";

  type ModularRestoreState = "idle" | "restoring" | "ready" | "failed";
  type UploadTaskKind = Extract<LearningTask["kind"], "native" | "visual" | "scratch" | "calliope" | "filius">;
  type UploadIntent = {
    storage_key: string;
    url: string;
    headers?: Record<string, string>;
  };
  type SubmissionHistoryLoadState = "not_loaded" | "loading" | "loaded" | "failed" | "unavailable";

  let { data, form }: { data: PageData; form: ActionData } = $props();

  let flowNodes = $state.raw<LearningFlowNode[]>([]);
  let flowEdges = $state.raw<TeacherFlowEdge[]>([]);
  let graphBusy = $state(false);
  let graphState = $state<LearningUnitGraph | null>(null);
  let modularWorkspace = $state<ModularWorkspaceState>(defaultModularWorkspaceState(currentViewportWidth()));
  let linearWorkspace = $state<LinearWorkspaceState>(defaultLinearWorkspaceState(currentViewportWidth()));
  let learnerWorkspace = $state<LearnerWorkspaceState>(defaultLearnerWorkspaceState());
  let moduleCache = $state.raw<Record<string, LearningModuleContent>>({});
  let moduleLoading = $state.raw<Record<string, boolean>>({});
  let moduleErrors = $state.raw<Record<string, string | null>>({});
  let workspaceReady = $state(false);
  let historyRestored = $state(false);
  let modularSettingsMenuOpen = $state(false);
  let layoutPreferences = $state<LayoutPreferences>(defaultLayoutPreferences(currentViewportWidth()));
  let workspaceRoot = $state<HTMLDivElement | null>(null);
  let submissionHistoryByTask = $state.raw<Record<string, LearningSubmission[]>>({});
  let submissionHistoryStateByTask = $state.raw<Record<string, SubmissionHistoryLoadState>>({});
  let reviewFocusByPane = $state<ReviewFocusByPane>(emptyReviewFocus());
  let submissionMessageState = $state<string | null>(null);
  let clientSubmissionErrorTaskId = $state<string | null>(null);
  let clientSubmissionErrorMessage = $state<string | null>(null);
  let feedbackPendingTaskId = $state<string | null>(null);
  let feedbackStatusTaskId = $state<string | null>(null);
  let feedbackStatusMessage = $state<string | null>(null);
  let pendingSubmissionIntent = $state<"feedback" | "submit" | null>(null);
  let modularRestoreState = $state<ModularRestoreState>("idle");
  let modularRestoreMessage = $state<string | null>(null);
  let feedbackPollToken = 0;

  let rebuildToken = 0;

  function isModularUnit(): boolean {
    return data.selectedUnit?.unit.unit_type === "modular";
  }

  function storageKey(): string {
    return learningUnitWorkspaceStorageKey(data.courseId, data.unitId);
  }

  function plainModule(module: LearningModuleContent): LearningModuleContent {
    return JSON.parse(JSON.stringify(module)) as LearningModuleContent;
  }

  function plainGraph(graph: LearningUnitGraph): LearningUnitGraph {
    return JSON.parse(JSON.stringify(graph)) as LearningUnitGraph;
  }

  function currentViewportWidth(): number {
    return browser ? window.innerWidth : 1280;
  }

  function graphModuleById(moduleId: string | null): LearningUnitGraphModule | null {
    if (!moduleId) {
      return null;
    }
    return graphState?.modules.find((module) => module.id === moduleId) ?? null;
  }

  function openableModuleIds(): Set<string> {
    return new Set(
      (graphState?.modules ?? [])
        .filter((module) => module.status === "open" || module.status === "done")
        .map((module) => module.id)
    );
  }

  function readStoredWorkspaceState(viewportWidth = currentViewportWidth()): {
    modular: ModularWorkspaceState;
    linear: LinearWorkspaceState;
    layout: LayoutPreferences;
  } {
    return readLearningUnitWorkspaceState({
      storage: browser ? window.localStorage : null,
      courseId: data.courseId,
      unitId: data.unitId,
      viewportWidth,
      openableModuleIds: openableModuleIds()
    });
  }

  function seedModularWorkspaceState(base: ModularWorkspaceState): ModularWorkspaceState {
    const seeded = normalizeModularWorkspaceState(base, openableModuleIds());
    const next = reconcileModularWorkspaceState(
      {
        view: seeded.view,
        openTabs: seeded.openTabs,
        activeTab: seeded.activeTab
      },
      {
        moduleOrder: (graphState?.modules ?? []).map((module) => module.id),
        openableModuleIds: openableModuleIds(),
        requestedView: data.initialView,
        requestedModuleId: data.activeModule?.module.id ?? null
      }
    );

    return {
      ...seeded,
      view: next.view,
      openTabs: next.openTabs,
      activeTab: next.activeTab
    };
  }

  function orderedOpenModulesForContent(): LearningUnitGraphModule[] {
    return orderedOpenModules(graphState, modularWorkspace.openTabs);
  }

  function contentGroups(): ContentGroup[] {
    if (isModularUnit()) {
      return contentGroupsForModules(graphState, modularWorkspace.openTabs, moduleCache);
    }

    return contentGroupsForSections(data.sections);
  }

  function currentContentItems(): LearningContentItem[] {
    return flattenContentGroups(contentGroups());
  }

  function contextModuleOptions(): Array<{
    id: string;
    title: string;
    current: boolean;
    loaded: boolean;
    loading: boolean;
    error: string | null;
    items: LearningContentItem[];
  }> {
    if (!isModularUnit()) {
      return contentGroups().map((group) => ({
        id: group.id,
        title: group.title ?? "Abschnitt",
        current: group.items.some((item) => item.key === learnerWorkspace.activeTask?.itemKey),
        loaded: true,
        loading: false,
        error: null,
        items: group.items
      }));
    }

    return (graphState?.modules ?? [])
      .filter((module) => module.status === "open" || module.status === "done")
      .map((module) => ({
        id: module.id,
        title: module.title,
        current: module.id === learnerWorkspace.activeTask?.moduleId,
        loaded: Boolean(moduleCache[module.id]),
        loading: Boolean(moduleLoading[module.id]),
        error: moduleErrors[module.id] ?? null,
        items: moduleContentItems(moduleCache[module.id] ?? null)
      }));
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

  function learnerStorageKeys() {
    return learnerWorkspaceStorageKeys(data.user?.sub ?? null, data.courseId, data.unitId);
  }

  function setLearnerWorkspaceState(next: LearnerWorkspaceState) {
    learnerWorkspace = next;
  }

  function beginTaskWorkspace(itemKey: string, editorMode: "text" | "upload") {
    const item = currentContentItems().find((candidate) => candidate.key === itemKey && candidate.task);
    if (!item?.task) {
      return;
    }

    setLearnerWorkspaceState({
      ...learnerWorkspace,
      mode: "working",
      activeTask: {
        itemKey,
        taskId: item.task.id,
        moduleId: item.moduleId ?? null,
        status: "editing",
        editorMode
      },
      context: {
        ...learnerWorkspace.context,
        compactSurface: "task"
      },
      returnPosition: {
        moduleId: item.moduleId ?? null,
        scrollY: browser ? window.scrollY : 0,
        focusId: `task-row-${item.task.id}`
      }
    });
  }

  async function leaveTaskWorkspace() {
    const position = learnerWorkspace.returnPosition;
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      mode: "orienting",
      activeTask: null,
      context: {
        ...learnerWorkspace.context,
        compactSurface: "task",
        readingReferenceKey: null
      }
    });

    await tick();
    if (!browser || !position) {
      return;
    }
    window.scrollTo({ top: position.scrollY, behavior: "auto" });
    if (position.focusId) {
      document.getElementById(position.focusId)?.focus({ preventScroll: true });
    }
  }

  function setCompactSurface(surface: "task" | "materials") {
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        compactSurface: surface
      }
    });
  }

  function toggleContextPicker() {
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        pickerOpen: !learnerWorkspace.context.pickerOpen
      }
    });
  }

  async function toggleContextModule(moduleId: string) {
    const expanded = learnerWorkspace.context.expandedModuleIds.includes(moduleId);
    const expandedModuleIds = expanded
      ? learnerWorkspace.context.expandedModuleIds.filter((id) => id !== moduleId)
      : [...learnerWorkspace.context.expandedModuleIds, moduleId];
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        expandedModuleIds
      }
    });
    if (!expanded && isModularUnit()) {
      await ensureModuleLoaded(moduleId);
    }
  }

  function addContextReference(reference: LearnerContextReference) {
    if (learnerWorkspace.context.manualReferences.some((entry) => entry.key === reference.key)) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        manualReferences: [...learnerWorkspace.context.manualReferences, reference]
      }
    });
  }

  function removeContextReference(referenceKey: string) {
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        manualReferences: learnerWorkspace.context.manualReferences.filter(
          (reference) => reference.key !== referenceKey
        ),
        expandedReferenceKeys: learnerWorkspace.context.expandedReferenceKeys.filter(
          (key) => key !== referenceKey
        ),
        readingReferenceKey:
          learnerWorkspace.context.readingReferenceKey === referenceKey
            ? null
            : learnerWorkspace.context.readingReferenceKey
      }
    });
  }

  async function openContextReference(referenceKey: string) {
    const reference = learnerWorkspace.context.manualReferences.find((entry) => entry.key === referenceKey);
    if (reference?.kind === "submission" && reference.taskId) {
      await ensureSubmissionHistoryLoaded(reference.taskId);
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        compactSurface: "materials",
        readingReferenceKey: referenceKey,
        scrollTop: 0
      }
    });
  }

  function closeContextReader() {
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        readingReferenceKey: null,
        scrollTop: 0
      }
    });
  }

  function rememberContextScroll(scrollTop: number) {
    if (Math.abs(learnerWorkspace.context.scrollTop - scrollTop) < 1) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        scrollTop: Math.max(0, scrollTop)
      }
    });
  }

  function markActiveTaskResult(taskId: string) {
    if (learnerWorkspace.activeTask?.taskId !== taskId) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      activeTask: {
        ...learnerWorkspace.activeTask,
        status: "result"
      }
    });
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

  function historyForTask(taskId: string): LearningSubmission[] {
    return submissionHistoryByTask[taskId] ?? [];
  }

  function setTaskHistory(taskId: string, entries: LearningSubmission[]) {
    submissionHistoryByTask = {
      ...submissionHistoryByTask,
      [taskId]: entries
    };
    setTaskHistoryState(taskId, entries.length ? "loaded" : "unavailable");
  }

  function setTaskHistoryState(taskId: string, state: SubmissionHistoryLoadState) {
    submissionHistoryStateByTask = {
      ...submissionHistoryStateByTask,
      [taskId]: state
    };
  }

  function syncModularWorkspaceUrl(view: LearningUnitViewState, moduleId: string | null) {
    if (!browser) {
      return;
    }

    const next = new URL(window.location.href);
    next.searchParams.set("view", view);
    if (view === "content" && moduleId) {
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

  function modularWorkspaceSnapshot(): ModularWorkspaceSnapshot {
    return {
      view: modularWorkspace.view,
      openTabs: modularWorkspace.openTabs,
      activeTab: modularWorkspace.activeTab
    };
  }

  async function fetchModularGraph(): Promise<LearningUnitGraph> {
    const response = await fetch(
      `/api/learning/courses/${encodeURIComponent(data.courseId)}/units/${encodeURIComponent(data.unitId)}/modules/graph`,
      {
        credentials: "include",
        cache: "no-store"
      }
    );
    if (handleRecoverableAuthResponse(response)) {
      throw new Error("auth_recovery_started");
    }
    if (!response.ok) {
      throw new Error(`graph_fetch_failed_${response.status}`);
    }
    return (await response.json()) as LearningUnitGraph;
  }

  function applyRefreshedGraph(nextGraph: LearningUnitGraph) {
    const openableIds = new Set(
      nextGraph.modules
        .filter((module) => module.status === "open" || module.status === "done")
        .map((module) => module.id)
    );
    const requestedView =
      modularWorkspace.view === "content" && modularWorkspace.activeTab && openableIds.has(modularWorkspace.activeTab)
        ? "content"
        : "overview";
    const next = reconcileModularWorkspaceState(modularWorkspaceSnapshot(), {
      moduleOrder: nextGraph.modules.map((module) => module.id),
      openableModuleIds: openableIds,
      requestedView,
      requestedModuleId: requestedView === "content" ? modularWorkspace.activeTab : null
    });

    graphState = plainGraph(nextGraph);
    setModularWorkspaceState({
      ...modularWorkspace,
      view: next.view,
      openTabs: next.openTabs,
      activeTab: next.activeTab
    });

    if (next.view === "content" && next.activeTab && !moduleCache[next.activeTab]) {
      void ensureModuleLoaded(next.activeTab);
    }

    syncModularWorkspaceUrl(next.view, next.view === "content" ? next.activeTab : null);
  }

  let graphRefreshInFlight: Promise<void> | null = null;

  async function refreshModularGraph() {
    if (!browser || !isModularUnit()) {
      return;
    }
    if (graphRefreshInFlight) {
      return graphRefreshInFlight;
    }

    graphRefreshInFlight = (async () => {
      const nextGraph = await fetchModularGraph();
      applyRefreshedGraph(nextGraph);
    })();

    try {
      await graphRefreshInFlight;
    } finally {
      graphRefreshInFlight = null;
    }
  }

  async function fetchModuleContent(moduleId: string): Promise<LearningModuleContent> {
    const response = await fetch(
      `/learning/courses/${encodeURIComponent(data.courseId)}/units/${encodeURIComponent(data.unitId)}/modules/${encodeURIComponent(moduleId)}?include=materials,tasks`,
      {
        credentials: "include",
        cache: "no-store"
      }
    );

    if (handleRecoverableAuthResponse(response)) {
      throw new Error("auth_recovery_started");
    }
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
      reopenModularMaterials(moduleIds);
      modularRestoreState = "ready";
      modularRestoreMessage = null;
      restoreHistoryContext();
      return;
    }

    modularRestoreState = "failed";
    modularRestoreMessage = "Die Inhalte konnten nicht vollständig wiederhergestellt werden. Du kannst offene Module im Graph erneut öffnen.";
  }

  function setModularWorkspaceState(next: ModularWorkspaceState) {
    modularWorkspace = next;
  }

  function setLinearWorkspaceState(next: LinearWorkspaceState) {
    linearWorkspace = next;
  }

  function applySubmissionFocus(nextValue: Record<PaneId, SubmissionFocusState>) {
    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        submissionFocus: nextValue
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      submissionFocus: nextValue
    });
  }

  function applyTaskDetailState(next: {
    submissionFocus: Record<PaneId, SubmissionFocusState>;
    reviewFocus: ReviewFocusByPane;
  }) {
    applySubmissionFocus(next.submissionFocus);
    reviewFocusByPane = next.reviewFocus;
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
      if (!nextValue) {
        reviewFocusByPane = { left: reviewFocusByPane.left, right: null };
      }
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
    if (!nextValue) {
      reviewFocusByPane = { left: reviewFocusByPane.left, right: null };
    }
  }

  function toggleToc() {
    const nextVisible = !learnerWorkspace.preferences.navigationVisible;
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      preferences: {
        ...learnerWorkspace.preferences,
        navigationVisible: nextVisible
      }
    });
    if (isModularUnit()) {
      setModularWorkspaceState({
        ...modularWorkspace,
        tocOpen: nextVisible
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      tocOpen: nextVisible
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

  function reopenModularMaterials(moduleIds: string[]) {
    if (!isModularUnit() || !moduleIds.length) {
      return;
    }

    const items = currentContentItems();
    const currentStacks = currentPaneStacks();
    const nextLeft = reopenMaterialEntries(currentStacks.left, items, moduleIds);
    const nextRight = reopenMaterialEntries(currentStacks.right, items, moduleIds);
    const changed = nextLeft.some((entry, index) => entry.expanded !== currentStacks.left[index]?.expanded)
      || nextRight.some((entry, index) => entry.expanded !== currentStacks.right[index]?.expanded);

    if (!changed) {
      return;
    }

    setModularWorkspaceState({
      ...modularWorkspace,
      paneStacks: {
        left: nextLeft,
        right: nextRight
      }
    });
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
    if (!itemKey || !mode) {
      applyTaskDetailState(setPaneSubmissionFocus(submissionFocusState(), reviewFocusByPane, paneId, null, null));
      return;
    }

    applyTaskDetailState(togglePaneSubmissionFocus(submissionFocusState(), reviewFocusByPane, paneId, itemKey, mode));
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

  function activeSubmissionErrorTaskId(): string | null {
    return clientSubmissionErrorTaskId ?? actionTaskId();
  }

  function activeSubmissionErrorMessage(): string | null {
    return clientSubmissionErrorTaskId ? clientSubmissionErrorMessage : (form?.message ?? null);
  }

  function setClientSubmissionError(taskId: string | null, message: string | null) {
    clientSubmissionErrorTaskId = taskId;
    clientSubmissionErrorMessage = message;
  }

  function clearSubmissionWorkspace() {
    applySubmissionFocus(emptySubmissionFocus());
  }

  function canonicalUploadMimeType(taskKind: UploadTaskKind, file: File): string {
    if (taskKind === "scratch") {
      return SCRATCH_SB3_MIME;
    }
    if (taskKind === "calliope") {
      return MAKECODE_HEX_MIME;
    }
    if (taskKind === "filius") {
      return FILIUS_FLS_MIME;
    }
    const fileType = String(file.type || "").trim().toLowerCase();
    if (fileType) {
      return fileType;
    }
    return taskKind === "visual" ? "image/png" : PDF_MIME;
  }

  async function createUploadSubmission(
    taskId: string,
    taskKind: UploadTaskKind,
    file: File,
    intent: UploadIntent,
    sha256: string
  ): Promise<{ id?: string | null }> {
    const mimeType = canonicalUploadMimeType(taskKind, file);
    const response = await fetch(
      `/api/learning/courses/${encodeURIComponent(data.courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`,
      {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "idempotency-key": crypto.randomUUID()
        },
        body: JSON.stringify({
          intent: "feedback",
          kind: mimeType.startsWith("image/") ? "image" : "file",
          storage_key: intent.storage_key,
          mime_type: mimeType,
          size_bytes: file.size,
          sha256
        })
      }
    );

    if (handleRecoverableAuthResponse(response)) {
      throw new Error("auth_recovery_started");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string; error?: string };
      throw new Error(payload.detail || payload.error || "submission_failed");
    }

    return (await response.json().catch(() => ({}))) as { id?: string | null };
  }

  async function loadSubmissionHistory(taskId: string): Promise<LearningSubmission[]> {
    const historyUrl = buildLearningSubmissionHistoryUrl(data.courseId, taskId);
    if (!historyUrl) {
      throw new Error("history_missing_context");
    }
    const response = await fetch(historyUrl, {
      credentials: "include",
      cache: "no-store"
    });
    if (handleRecoverableAuthResponse(response)) {
      return [];
    }
    if (!response.ok) {
      throw new Error(`history_failed_${response.status}`);
    }
    return (await response.json()) as LearningSubmission[];
  }

  function handleRecoverableAuthResponse(response: Response): boolean {
    if (!browser) {
      return false;
    }
    return handleBrowserAuthRecovery(response);
  }

  async function ensureSubmissionHistoryLoaded(taskId: string): Promise<LearningSubmission[]> {
    const currentState = submissionHistoryStateByTask[taskId] ?? "not_loaded";
    const currentEntries = historyForTask(taskId);
    if (currentEntries.length && currentState !== "failed") {
      return currentEntries;
    }

    setTaskHistoryState(taskId, "loading");
    feedbackStatusTaskId = taskId;
    feedbackStatusMessage = "Die Abgabe wird geladen ...";

    try {
      const entries = await loadSubmissionHistory(taskId);
      setTaskHistory(taskId, entries);
      feedbackStatusTaskId = entries.length ? null : taskId;
      feedbackStatusMessage = entries.length ? null : "Für diese Aufgabe gibt es noch keine gespeicherte Abgabe.";
      return entries;
    } catch (caught) {
      const reason = caught instanceof Error ? caught.message : "history_failed";
      setTaskHistoryState(taskId, "failed");
      feedbackStatusTaskId = taskId;
      if (reason === "history_missing_context") {
        feedbackStatusMessage = MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE;
        return [];
      }
      feedbackStatusMessage = "Der Verlauf konnte nicht geladen werden. Bitte versuche es erneut.";
      return [];
    }
  }

  async function pollFeedbackSubmission(
    taskId: string,
    submissionId: string | null,
    intent: "feedback" | "submit",
    paneId: PaneId
  ) {
    const pollToken = ++feedbackPollToken;
    const fastPollAttempts = 30;
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
          setTaskHistory(taskId, entries);
          submissionMessageState = "feedback";
          feedbackPendingTaskId = null;
          feedbackStatusTaskId = null;
          feedbackStatusMessage = null;
          pendingSubmissionIntent = null;
          applyTaskDetailState(setPaneReviewFocus(submissionFocusState(), reviewFocusByPane, paneId, taskItemKey(taskId)));
          if (intent === "submit") {
            markActiveTaskResult(taskId);
          }
          await refreshModularGraph().catch(() => undefined);
          return;
        }

        if (matchingSubmission?.analysis_status === "failed") {
          setTaskHistory(taskId, entries);
          feedbackPendingTaskId = null;
          feedbackStatusTaskId = taskId;
          pendingSubmissionIntent = null;
          feedbackStatusMessage = learningSubmissionFailureMessage(
            matchingSubmission,
            intent === "submit"
              ? "Die Auswertung konnte nicht erstellt werden."
              : "Die Rückmeldung konnte nicht erstellt werden."
          );
          return;
        }
      } catch (caught) {
        if (pollToken !== feedbackPollToken) {
          return;
        }
        const reason = caught instanceof Error ? caught.message : "history_failed";
        if (reason === "history_missing_context") {
          setTaskHistoryState(taskId, "failed");
          feedbackPendingTaskId = null;
          feedbackStatusTaskId = taskId;
          pendingSubmissionIntent = null;
          feedbackStatusMessage = MISSING_SUBMISSION_HISTORY_CONTEXT_MESSAGE;
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

  async function submitUploadFeedback(payload: {
    taskId: string;
    taskKind: UploadTaskKind;
    file: File;
    moduleId: string | null;
    paneId: PaneId;
  }) {
    const { taskId, taskKind, file, paneId } = payload;

    setClientSubmissionError(null, null);
    submissionMessageState = null;
    feedbackPendingTaskId = taskId;
    feedbackStatusTaskId = taskId;
    pendingSubmissionIntent = "feedback";
    feedbackStatusMessage = "Rückmeldung wird erstellt ...";

    try {
      const mimeType = canonicalUploadMimeType(taskKind, file);
      const prepared = await prepareBrowserStorageUpload({
        intentUrl: `/api/learning/courses/${encodeURIComponent(data.courseId)}/tasks/${encodeURIComponent(taskId)}/upload-intents`,
        intentPayload: {
          kind: mimeType.startsWith("image/") ? "image" : "file",
          filename: file.name || "submission.bin",
          mime_type: mimeType,
          size_bytes: file.size
        },
        file,
        fallbackMimeType: mimeType,
        onAuthRecovery: handleBrowserAuthRecovery
      });
      const submission = await createUploadSubmission(taskId, taskKind, file, prepared.intent as UploadIntent, prepared.sha256);
      await refreshModularGraph().catch(() => undefined);
      await pollFeedbackSubmission(taskId, submission.id ?? null, "feedback", paneId);
    } catch (caught) {
      feedbackPendingTaskId = null;
      feedbackStatusTaskId = taskId;
      pendingSubmissionIntent = null;

      const reason = caught instanceof Error ? caught.message : "upload_failed";
      if (reason === "invalid_upload_content") {
        feedbackStatusMessage = "Die Datei passt nicht zum erwarteten Dateityp. Bitte wähle die richtige Datei aus.";
        setClientSubmissionError(taskId, "Die Datei passt nicht zum erwarteten Dateityp. Bitte wähle die richtige Datei aus.");
        return;
      }
      if (reason === "invalid_image_payload" || reason === "invalid_file_payload") {
        feedbackStatusMessage = "Die Datei ist für diese Aufgabe nicht zulässig.";
        setClientSubmissionError(taskId, "Die Datei ist für diese Aufgabe nicht zulässig.");
        return;
      }
      if (reason === "max_upload_size_exceeded") {
        feedbackStatusMessage = "Die Datei ist zu groß.";
        setClientSubmissionError(taskId, "Die Datei ist zu groß.");
        return;
      }
      if (reason === "upload_failed") {
        feedbackStatusMessage = "Die Datei konnte nicht hochgeladen werden.";
        setClientSubmissionError(taskId, "Die Datei konnte nicht hochgeladen werden.");
        return;
      }
      if (reason === "auth_recovery_started") {
        feedbackStatusMessage = null;
        setClientSubmissionError(taskId, null);
        return;
      }
      feedbackStatusMessage = "Die Rückmeldung konnte nicht angefordert werden.";
      setClientSubmissionError(taskId, "Die Rückmeldung konnte nicht angefordert werden.");
    }
  }

  async function handleProgressPersisted() {
    const activeTaskId = learnerWorkspace.activeTask?.taskId ?? null;
    if (activeTaskId) {
      await ensureSubmissionHistoryLoaded(activeTaskId);
      markActiveTaskResult(activeTaskId);
    }
    await refreshModularGraph().catch(() => undefined);
  }

  function enhanceTaskForm(taskId: string, paneId: PaneId): SubmitFunction {
    return ({ submitter }) => {
      if (!(submitter instanceof HTMLButtonElement)) {
        return;
      }

      const intent = submitter.value === "feedback" ? "feedback" : "submit";
      setClientSubmissionError(null, null);
      if (intent === "feedback") {
        feedbackPendingTaskId = taskId;
        feedbackStatusTaskId = taskId;
        pendingSubmissionIntent = intent;
        feedbackStatusMessage = "Rückmeldung wird erstellt ...";
      }

      return async ({ result }) => {
        if (result.type === "success") {
          const payload = (result.data ?? {}) as {
            feedbackRequestedTaskId?: string;
            feedbackSubmissionId?: string | null;
            finalizedTaskId?: string;
            finalizedSubmission?: LearningSubmission | null;
            pendingIntent?: "feedback" | "submit";
            message?: string;
          };
          if (payload.finalizedTaskId && payload.finalizedSubmission) {
            applyTaskDetailState(setPaneSubmissionFocus(submissionFocusState(), reviewFocusByPane, paneId, null, null));
            setTaskHistory(payload.finalizedTaskId, [
              payload.finalizedSubmission,
              ...historyForTask(payload.finalizedTaskId).filter((entry) => entry.id !== payload.finalizedSubmission?.id)
            ]);
            applyTaskDetailState(setPaneReviewFocus(submissionFocusState(), reviewFocusByPane, paneId, null));
            submissionMessageState = payload.message ?? "submitted";
            feedbackPendingTaskId = null;
            feedbackStatusTaskId = null;
            pendingSubmissionIntent = null;
            feedbackStatusMessage = null;
            markActiveTaskResult(payload.finalizedTaskId);
            await refreshModularGraph().catch(() => undefined);
            return;
          }
          await refreshModularGraph().catch(() => undefined);
          await pollFeedbackSubmission(
            payload.feedbackRequestedTaskId ?? taskId,
            payload.feedbackSubmissionId ?? null,
            payload.pendingIntent ?? intent,
            paneId
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
            (intent === "submit" ? "Die finale Abgabe konnte nicht erstellt werden." : "Die Rückmeldung konnte nicht angefordert werden.");
          return;
        }

        await applyAction(result);
      };
    };
  }

  async function toggleReviewPanel(paneId: PaneId, taskId: string) {
    const itemKey = taskItemKey(taskId);
    const nextOpen = reviewFocusByPane[paneId] !== itemKey;
    if (!nextOpen) {
      applyTaskDetailState(setPaneReviewFocus(submissionFocusState(), reviewFocusByPane, paneId, null));
      return;
    }

    const entries = await ensureSubmissionHistoryLoaded(taskId);
    if (!entries.length && submissionHistoryStateByTask[taskId] !== "loaded") {
      return;
    }

    applyTaskDetailState(setPaneReviewFocus(submissionFocusState(), reviewFocusByPane, paneId, itemKey));
  }

  function openModule(moduleId: string) {
    const module = graphModuleById(moduleId);
    if (!module || (module.status !== "open" && module.status !== "done")) {
      return;
    }

    const moduleAlreadyLoaded = Boolean(moduleCache[moduleId]);
    const openTabs = modularWorkspace.openTabs.includes(moduleId)
      ? modularWorkspace.openTabs
      : [...modularWorkspace.openTabs, moduleId];

    setModularWorkspaceState({
      ...modularWorkspace,
      view: "content",
      openTabs,
      activeTab: moduleId
    });
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      openedModuleIds: openTabs
    });
    modularRestoreState = "ready";
    modularRestoreMessage = null;
    syncModularWorkspaceUrl("content", moduleId);

    if (moduleAlreadyLoaded) {
      reopenModularMaterials([moduleId]);
      return;
    }

    void ensureModuleLoaded(moduleId).then((loaded) => {
      if (loaded) {
        reopenModularMaterials([moduleId]);
      }
    });
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
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      openedModuleIds: remaining,
      mode:
        learnerWorkspace.activeTask?.moduleId === moduleId ? "orienting" : learnerWorkspace.mode,
      activeTask:
        learnerWorkspace.activeTask?.moduleId === moduleId ? null : learnerWorkspace.activeTask
    });
    syncModularWorkspaceUrl(nextActive ? "content" : "overview", nextActive);
  }

  function switchView(view: LearningUnitViewState) {
    modularSettingsMenuOpen = false;
    setModularWorkspaceState({
      ...modularWorkspace,
      view
    });
    syncModularWorkspaceUrl(view, view === "content" ? modularWorkspace.activeTab : null);
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
    const nextScale = value <= 0.95 ? 0.9 : value >= 1.1 ? 1.15 : 1;
    applyFontScale(nextScale);
    updateLayoutPreferences({ fontScale: nextScale });
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      preferences: {
        ...learnerWorkspace.preferences,
        fontSize: nextScale === 0.9 ? "small" : nextScale === 1.15 ? "large" : "standard"
      }
    });
  }

  function resetLayoutPreferences() {
    const viewportWidth = currentViewportWidth();
    const layoutDefaults = defaultLayoutPreferences(viewportWidth);
    const chromeDefaults = defaultWorkspaceChrome(viewportWidth);

    layoutPreferences = layoutDefaults;
    applyWorkspaceWidth(layoutDefaults.workspaceWidth);
    applyFontScale(layoutDefaults.fontScale);
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      preferences: {
        navigationVisible: chromeDefaults.tocOpen,
        fontSize: "standard"
      }
    });

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
    if (!isModularUnit() || !graphState || !data.user) {
      flowNodes = [];
      flowEdges = [];
      return;
    }

    const token = ++rebuildToken;
    graphBusy = true;

    try {
      const flow = await buildLearningUnitFlow(
        graphState,
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
    openItemInPane(itemKey, "left", { activatePane: true, scroll: true });
    applyTaskDetailState(setPaneReviewFocus(submissionFocusState(), reviewFocusByPane, "left", itemKey));
  }

  onMount(() => {
    const viewportWidth = currentViewportWidth();
    graphState = data.graph ? plainGraph(data.graph) : null;

    if (data.activeModule) {
      moduleCache = {
        [data.activeModule.module.id]: plainModule(data.activeModule)
      };
    }

    const stored = readLearnerWorkspaceState({
      localStorage: window.localStorage,
      sessionStorage: window.sessionStorage,
      learnerSub: data.user?.sub ?? null,
      courseId: data.courseId,
      unitId: data.unitId,
      openableModuleIds: openableModuleIds(),
      accessibleTaskKeys: isModularUnit()
        ? undefined
        : new Set(currentContentItems().filter((item) => item.kind === "task").map((item) => item.key)),
      accessibleReferenceKeys: isModularUnit()
        ? undefined
        : new Set(currentContentItems().filter((item) => item.kind === "material").map((item) => item.key))
    });
    setLearnerWorkspaceState(stored);
    const layoutDefaults = defaultLayoutPreferences(viewportWidth);
    layoutPreferences = {
      ...layoutDefaults,
      fontScale: stored.preferences.fontSize === "small" ? 0.9 : stored.preferences.fontSize === "large" ? 1.15 : 1
    };

    if (isModularUnit()) {
      const seeded = seedModularWorkspaceState({
        ...defaultModularWorkspaceState(viewportWidth),
        view: data.initialView,
        openTabs: stored.openedModuleIds,
        activeTab: data.activeModule?.module.id ?? stored.openedModuleIds[0] ?? null,
        tocOpen: stored.preferences.navigationVisible
      });
      setModularWorkspaceState(seeded);
      setLearnerWorkspaceState({ ...stored, openedModuleIds: seeded.openTabs });
      if (seeded.view === "content" && seeded.openTabs.length > 0) {
        void restoreOpenModules(seeded.openTabs);
      } else {
        modularRestoreState = "idle";
      }
    } else {
      setLinearWorkspaceState({
        ...defaultLinearWorkspaceState(viewportWidth),
        tocOpen: stored.preferences.navigationVisible
      });
    }

    applyWorkspaceWidth(layoutPreferences.workspaceWidth);
    applyFontScale(layoutPreferences.fontScale);
    workspaceReady = true;
    if (!isModularUnit()) {
      restoreHistoryContext();
    }
  });

  $effect(() => {
    graphState = data.graph ? plainGraph(data.graph) : null;
  });

  $effect(() => {
    if (data.historyTaskId) {
      setTaskHistory(data.historyTaskId, data.history);
    }
    submissionMessageState = data.message;
  });

  $effect(() => {
    if (!browser || !workspaceReady) {
      return;
    }

    const keys = learnerStorageKeys();
    if (!keys) {
      return;
    }
    window.localStorage.setItem(keys.persistent, serializeLearnerWorkspacePersistentState(learnerWorkspace));
    window.sessionStorage.setItem(keys.tab, serializeLearnerWorkspaceTabState(learnerWorkspace));
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

    const item = currentContentItems().find((candidate) => candidate.key === itemKey);
    if (!item?.task) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      mode: "working",
      activeTask: {
        itemKey,
        taskId: item.task.id,
        moduleId: item.moduleId ?? null,
        status: "result",
        editorMode: null
      }
    });
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

  $effect(() => {
    if (!workspaceReady || !learnerWorkspace.activeTask) {
      return;
    }
    if (isModularUnit() && modularRestoreState !== "ready") {
      return;
    }
    const availableTaskKeys = new Set(
      currentContentItems().filter((item) => item.kind === "task").map((item) => item.key)
    );
    if (!availableTaskKeys.has(learnerWorkspace.activeTask.itemKey)) {
      setLearnerWorkspaceState({
        ...learnerWorkspace,
        mode: "orienting",
        activeTask: null
      });
    }
  });
</script>

<svelte:document
  onclick={(event) => {
    const target = event.target;
    if (!(target instanceof Element) || !target.closest("[data-layout-menu-root]")) {
      modularSettingsMenuOpen = false;
    }
  }}
  onkeydown={(event) => {
    if (event.key === "Escape") {
      modularSettingsMenuOpen = false;
    }
  }}
/>

<svelte:head>
  <title>{data.selectedUnit?.unit.title ?? "Lernraum"} | GUSTAV</title>
</svelte:head>

<div bind:this={workspaceRoot} class="workspace-page workspace-page--learner-unit-content learning-unit-space">
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
      <div class="learning-unit-layout-frame learning-unit-layout-frame--toolbar">
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
                fontScale={layoutPreferences.fontScale}
                onToggleMenu={() => {
                  modularSettingsMenuOpen = !modularSettingsMenuOpen;
                }}
                onToggleToc={toggleToc}
                onResetLayout={resetLayoutPreferences}
                onCommitFontScale={commitFontScale}
              />
            </div>
          {/if}
        </div>
      </div>
    </section>

    {#if modularWorkspace.view === "overview"}
      <LearningUnitOverview graph={graphState} nodes={flowNodes} edges={flowEdges} />
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
              <LearnerContentWorkspace
                learnerSub={data.user?.sub ?? null}
                courseId={data.courseId}
                unitTitle={data.selectedUnit?.unit.title ?? "Lerneinheit"}
                unitType="modular"
                contentGroups={contentGroups()}
                mode={learnerWorkspace.mode}
                activeTaskKey={learnerWorkspace.activeTask?.itemKey ?? null}
                activeEditorMode={learnerWorkspace.activeTask?.editorMode ?? null}
                workStatus={learnerWorkspace.activeTask?.status ?? "editing"}
                compactSurface={learnerWorkspace.context.compactSurface}
                navigationVisible={learnerWorkspace.preferences.navigationVisible}
                contextModules={contextModuleOptions()}
                manualContextReferences={learnerWorkspace.context.manualReferences}
                contextPickerOpen={learnerWorkspace.context.pickerOpen}
                expandedContextModuleIds={learnerWorkspace.context.expandedModuleIds}
                readingReferenceKey={learnerWorkspace.context.readingReferenceKey}
                contextScrollTop={learnerWorkspace.context.scrollTop}
                historyByTask={submissionHistoryByTask}
                historyStateByTask={submissionHistoryStateByTask}
                submittedTaskId={data.submittedTaskId}
                submissionMessage={submissionMessageState}
                submissionErrorTaskId={activeSubmissionErrorTaskId()}
                submissionErrorMessage={activeSubmissionErrorMessage()}
                {feedbackPendingTaskId}
                {feedbackStatusTaskId}
                {feedbackStatusMessage}
                {pendingSubmissionIntent}
                enhanceTaskForm={(taskId) => enhanceTaskForm(taskId, "left")}
                onSubmitUploadFeedback={(payload) => submitUploadFeedback({ ...payload, paneId: "left" })}
                onBeginTask={beginTaskWorkspace}
                onPauseTask={leaveTaskWorkspace}
                onCloseModule={removeOpenModule}
                onSetCompactSurface={setCompactSurface}
                onToggleMaterial={(itemKey) => togglePaneItem("left", itemKey)}
                onToggleContextPicker={toggleContextPicker}
                onToggleContextModule={toggleContextModule}
                onAddContextReference={addContextReference}
                onRemoveContextReference={removeContextReference}
                onOpenContextReference={openContextReference}
                onCloseContextReader={closeContextReader}
                onContextScroll={rememberContextScroll}
                onToggleReviewPanel={(taskId) => toggleReviewPanel("left", taskId)}
                onProgressPersisted={handleProgressPersisted}
              />
            {/if}
          </section>
        </div>
      </div>
    {/if}
  {:else}
    <div class="learning-unit-layout-rail">
      <div class="learning-unit-layout-frame">
        <section class="learning-unit-stage learning-unit-stage--content">
          <LearnerContentWorkspace
            learnerSub={data.user?.sub ?? null}
            courseId={data.courseId}
            unitTitle={data.selectedUnit?.unit.title ?? "Lerneinheit"}
            unitType="linear"
            contentGroups={contentGroups()}
            mode={learnerWorkspace.mode}
            activeTaskKey={learnerWorkspace.activeTask?.itemKey ?? null}
            activeEditorMode={learnerWorkspace.activeTask?.editorMode ?? null}
            workStatus={learnerWorkspace.activeTask?.status ?? "editing"}
            compactSurface={learnerWorkspace.context.compactSurface}
            navigationVisible={learnerWorkspace.preferences.navigationVisible}
            contextModules={contextModuleOptions()}
            manualContextReferences={learnerWorkspace.context.manualReferences}
            contextPickerOpen={learnerWorkspace.context.pickerOpen}
            expandedContextModuleIds={learnerWorkspace.context.expandedModuleIds}
            readingReferenceKey={learnerWorkspace.context.readingReferenceKey}
            contextScrollTop={learnerWorkspace.context.scrollTop}
            historyByTask={submissionHistoryByTask}
            historyStateByTask={submissionHistoryStateByTask}
            submittedTaskId={data.submittedTaskId}
            submissionMessage={submissionMessageState}
            submissionErrorTaskId={activeSubmissionErrorTaskId()}
            submissionErrorMessage={activeSubmissionErrorMessage()}
            {feedbackPendingTaskId}
            {feedbackStatusTaskId}
            {feedbackStatusMessage}
            {pendingSubmissionIntent}
            enhanceTaskForm={(taskId) => enhanceTaskForm(taskId, "left")}
            onSubmitUploadFeedback={(payload) => submitUploadFeedback({ ...payload, paneId: "left" })}
            onBeginTask={beginTaskWorkspace}
            onPauseTask={leaveTaskWorkspace}
            onCloseModule={() => {}}
            onSetCompactSurface={setCompactSurface}
            onToggleMaterial={(itemKey) => togglePaneItem("left", itemKey)}
            onToggleContextPicker={toggleContextPicker}
            onToggleContextModule={toggleContextModule}
            onAddContextReference={addContextReference}
            onRemoveContextReference={removeContextReference}
            onOpenContextReference={openContextReference}
            onCloseContextReader={closeContextReader}
            onContextScroll={rememberContextScroll}
            onToggleReviewPanel={(taskId) => toggleReviewPanel("left", taskId)}
            onProgressPersisted={handleProgressPersisted}
          />
        </section>
      </div>
    </div>
  {/if}
</div>
