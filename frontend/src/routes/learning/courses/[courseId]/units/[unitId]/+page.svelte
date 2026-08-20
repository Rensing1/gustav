<script lang="ts">
  import { applyAction } from "$app/forms";
  import { browser } from "$app/environment";
  import { onMount, tick, untrack } from "svelte";

  import WorkspaceSettingsMenu from "$lib/components/ui/WorkspaceSettingsMenu.svelte";
  import StatusMessage from "$lib/components/ui/StatusMessage.svelte";
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
    flattenContentGroups,
    moduleContentItems,
    sectionContentItems,
    type ModularWorkspaceSnapshot,
    orderedOpenModules,
    reconcileModularWorkspaceState,
    type ContentGroup,
    type LearnerMaterialContextModule,
    type LearningContentItem
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
    defaultLearnerWorkspaceState,
    learningPathState,
    learnerWorkspaceStorageKeys,
    readLearnerWorkspaceState,
    serializeLearnerWorkspacePersistentState,
    serializeLearnerWorkspaceTabState,
    type LearnerWorkspaceState
  } from "$lib/learning-unit/learner-workspace-state";
  import { learnerNavigationHref } from "$lib/learning-unit/learner-navigation";
  import {
    readTaskColumnRatio,
    removeTaskColumnRatio,
    writeTaskColumnRatio
  } from "$lib/learning-unit/task-column-preference";
  import { highlightedLearnerGraphModuleIds } from "$lib/learning-unit/graph-selection";
  import { beginSubmissionAttempt } from "$lib/learning-unit/submission-finalization";
  import { clearSubmissionDraft } from "$lib/learning-unit/submission-drafts";
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
  type ClosedModuleSnapshot = {
    moduleId: string;
    title: string;
    index: number;
    previousActiveTab: string | null;
    expanded: boolean;
    expandedMaterialKeys: string[] | null;
    submissionsExpanded: boolean;
    expandedSubmissionKeys: string[];
    readingReferenceKey: string | null;
  };

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
  let taskColumnRatio = $state<number | null>(null);
  let workspaceRoot = $state<HTMLDivElement | null>(null);
  let submissionHistoryByTask = $state.raw<Record<string, LearningSubmission[]>>({});
  let submissionHistoryStateByTask = $state.raw<Record<string, SubmissionHistoryLoadState>>({});
  const pendingSubmissionHistoryLoads = new Map<string, Promise<LearningSubmission[]>>();
  let submissionMessageState = $state<string | null>(null);
  let clientSubmissionErrorTaskId = $state<string | null>(null);
  let clientSubmissionErrorMessage = $state<string | null>(null);
  let feedbackPendingTaskId = $state<string | null>(null);
  let feedbackStatusTaskId = $state<string | null>(null);
  let feedbackStatusMessage = $state<string | null>(null);
  let pendingSubmissionIntent = $state<"feedback" | "submit" | null>(null);
  let modularRestoreState = $state<ModularRestoreState>("idle");
  let modularRestoreMessage = $state<string | null>(null);
  let closedModuleSnapshot = $state<ClosedModuleSnapshot | null>(null);
  let feedbackPollToken = 0;
  let closedModuleUndoTimer: number | null = null;

  let rebuildToken = 0;
  function isModularUnit(): boolean {
    return data.selectedUnit?.unit.unit_type === "modular";
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

  function contextModuleOptions(): LearnerMaterialContextModule[] {
    const activeModuleId = learnerWorkspace.activeTask?.moduleId ?? null;
    if (!isModularUnit()) {
      const sections = data.sections.map((section) => {
        const items = sectionContentItems(section);
        return {
          id: section.section.id,
          title: section.section.title || `Abschnitt ${section.section.position}`,
          current: items.some((item) => item.key === learnerWorkspace.activeTask?.itemKey),
          closable: false,
          loaded: true,
          loading: false,
          error: null,
          items
        } satisfies LearnerMaterialContextModule;
      });
      return [
        ...sections.filter((section) => section.current),
        ...sections.filter((section) => !section.current)
      ];
    }

    const openedModules = orderedOpenModulesForContent();
    const activeFirst = [
      ...openedModules.filter((module) => module.id === activeModuleId),
      ...openedModules.filter((module) => module.id !== activeModuleId)
    ];
    return activeFirst
      .map((module) => ({
        id: module.id,
        title: module.title,
        current: module.id === activeModuleId,
        closable: module.id !== activeModuleId,
        loaded: Boolean(moduleCache[module.id]),
        loading: Boolean(moduleLoading[module.id]),
        error: moduleErrors[module.id] ?? null,
        items: moduleContentItems(moduleCache[module.id] ?? null)
      }));
  }

  function workspaceTocOpen(): boolean {
    return isModularUnit() ? modularWorkspace.tocOpen : linearWorkspace.tocOpen;
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

  async function beginTaskWorkspace(itemKey: string, editorMode: "text" | "upload") {
    const item = currentContentItems().find((candidate) => candidate.key === itemKey && candidate.task);
    if (!item?.task) {
      return;
    }

    if (item.task.has_submission) {
      await ensureSubmissionHistoryLoaded(item.task.id);
    }

    setLearnerWorkspaceState({
      ...learnerWorkspace,
      surface: "task",
      activeTask: {
        itemKey,
        taskId: item.task.id,
        moduleId: item.moduleId ?? null,
        status: "editing",
        editorMode
      },
      context: {
        ...learnerWorkspace.context,
        compactSurface: "task",
        expandedContextModuleIds: item.moduleId
          ? [...new Set([...learnerWorkspace.context.expandedContextModuleIds, item.moduleId])]
          : learnerWorkspace.context.expandedContextModuleIds
      },
      returnPosition: {
        moduleId: item.moduleId ?? null,
        scrollY: browser ? window.scrollY : 0,
        focusId: `task-row-${item.task.id}`
      }
    });
    syncLearnerNavigation({
      surface: "task",
      moduleId: item.moduleId ?? null,
      taskId: item.task.id,
      panel: null
    }, "push");
    await tick();
    window.scrollTo({ top: 0, behavior: "auto" });
    document.getElementById("learner-task-back")?.focus({ preventScroll: true });
  }

  async function leaveTaskWorkspace() {
    const position = learnerWorkspace.returnPosition;
    if (browser && window.history.state?.gustavLearnerSurface === "task") {
      window.history.back();
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      surface: "reading",
      context: {
        ...learnerWorkspace.context,
        compactSurface: "task",
        readingReferenceKey: null
      }
    });

    syncLearnerNavigation({
      surface: "reading",
      moduleId: position?.moduleId ?? learnerWorkspace.activeTask?.moduleId ?? null,
      taskId: null,
      panel: null
    }, "replace");

    await tick();
    if (!browser || !position) {
      return;
    }
    window.scrollTo({ top: position.scrollY, behavior: "auto" });
    if (position.focusId) {
      document.getElementById(position.focusId)?.focus({ preventScroll: true });
    }
  }

  function syncLearnerNavigation(
    target: { surface: "graph" | "reading" | "task"; moduleId: string | null; taskId: string | null; panel: "result" | null },
    historyMode: "push" | "replace"
  ) {
    if (!browser) return;
    const href = learnerNavigationHref(new URL(window.location.href), target);
    const state = { ...window.history.state, gustavLearnerSurface: target.surface };
    if (historyMode === "push") window.history.pushState(state, "", href);
    else window.history.replaceState(state, "", href);
  }

  function showLearningPath() {
    if (learnerWorkspace.surface === "task" && learnerWorkspace.activeTask) {
      setLearnerWorkspaceState(learningPathState(learnerWorkspace));
      syncLearnerNavigation({ surface: "graph", moduleId: null, taskId: null, panel: null }, "push");
      return;
    }
    if (browser && window.history.state?.gustavLearnerSurface === "reading") {
      window.history.back();
      return;
    }
    setLearnerWorkspaceState({ ...learnerWorkspace, surface: "graph", activeTask: null });
    syncLearnerNavigation({ surface: "graph", moduleId: null, taskId: null, panel: null }, "replace");
  }

  async function restoreSurfaceFromUrl() {
    if (!browser) return;
    const url = new URL(window.location.href);
    const requestedModuleId = url.searchParams.get("module");
    const requestedTaskId = url.searchParams.get("task") ?? url.searchParams.get("history");
    const resultRequested =
      url.searchParams.get("panel") === "result" ||
      url.searchParams.has("history") ||
      Boolean(requestedTaskId && requestedTaskId === actionTaskId());

    if (isModularUnit()) {
      if (!requestedModuleId || !openableModuleIds().has(requestedModuleId)) {
        setLearnerWorkspaceState({
          ...learnerWorkspace,
          surface: "graph",
          activeTask: null
        });
        syncLearnerNavigation({ surface: "graph", moduleId: null, taskId: null, panel: null }, "replace");
        return;
      }
      if (!modularWorkspace.openTabs.includes(requestedModuleId)) {
        const openTabs = [...modularWorkspace.openTabs, requestedModuleId];
        setModularWorkspaceState({ ...modularWorkspace, view: "content", openTabs, activeTab: requestedModuleId });
        setLearnerWorkspaceState({ ...learnerWorkspace, openedModuleIds: openTabs });
      }
      if (!moduleCache[requestedModuleId] && !(await ensureModuleLoaded(requestedModuleId))) return;
    }

    const requestedItem = requestedTaskId
      ? currentContentItems().find((item) => item.task?.id === requestedTaskId) ?? null
      : null;
    if (requestedTaskId && !requestedItem?.task) {
      setLearnerWorkspaceState({ ...learnerWorkspace, surface: "reading", activeTask: null });
      syncLearnerNavigation({ surface: "reading", moduleId: requestedModuleId, taskId: null, panel: null }, "replace");
      return;
    }

    const returnPosition = learnerWorkspace.returnPosition;
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      surface: requestedItem?.task ? "task" : "reading",
      activeTask: requestedItem?.task
        ? {
            itemKey: requestedItem.key,
            taskId: requestedItem.task.id,
            moduleId: requestedItem.moduleId ?? null,
            status: resultRequested ? "result" : "editing",
            editorMode: null
          }
        : learnerWorkspace.activeTask &&
            (learnerWorkspace.activeTask.moduleId === requestedModuleId || !isModularUnit())
          ? learnerWorkspace.activeTask
          : null
    });
    syncLearnerNavigation({
      surface: requestedItem?.task ? "task" : "reading",
      moduleId: requestedModuleId,
      taskId: requestedItem?.task?.id ?? null,
      panel: requestedItem?.task && resultRequested ? "result" : null
    }, "replace");
    if (!requestedItem?.task && returnPosition) {
      await tick();
      window.scrollTo({ top: returnPosition.scrollY, behavior: "auto" });
      if (returnPosition.focusId) {
        document.getElementById(returnPosition.focusId)?.focus({ preventScroll: true });
      }
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

  function toggleReadingMaterial(itemKey: string) {
    const collapsedItemKeys = learnerWorkspace.collapsedItemKeys.includes(itemKey)
      ? learnerWorkspace.collapsedItemKeys.filter((key) => key !== itemKey)
      : [...learnerWorkspace.collapsedItemKeys, itemKey];
    setLearnerWorkspaceState({ ...learnerWorkspace, collapsedItemKeys });
  }

  function toggleContextModuleMaterial(moduleId: string, itemKey: string) {
    const moduleMaterialKeys = contextModuleOptions()
      .find((module) => module.id === moduleId)
      ?.items.filter((item) => item.kind === "material")
      .map((item) => item.key) ?? [];
    const storedKeys = learnerWorkspace.context.expandedModuleMaterialKeys[moduleId];
    const expandedKeys = storedKeys ?? moduleMaterialKeys.slice(0, 1);
    const nextKeys = expandedKeys.includes(itemKey)
      ? expandedKeys.filter((key) => key !== itemKey)
      : [...expandedKeys, itemKey];

    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        expandedModuleMaterialKeys: {
          ...learnerWorkspace.context.expandedModuleMaterialKeys,
          [moduleId]: nextKeys
        }
      }
    });
  }

  async function toggleContextModule(moduleId: string) {
    if (moduleId === learnerWorkspace.activeTask?.moduleId) return;
    const expanded = learnerWorkspace.context.expandedContextModuleIds.includes(moduleId);
    const expandedContextModuleIds = expanded
      ? learnerWorkspace.context.expandedContextModuleIds.filter((id) => id !== moduleId)
      : [...learnerWorkspace.context.expandedContextModuleIds, moduleId];
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        expandedContextModuleIds
      }
    });
    if (!expanded && isModularUnit()) {
      await ensureModuleLoaded(moduleId);
    }
  }

  async function toggleContextSubmissions(moduleId: string) {
    const expanded = learnerWorkspace.context.expandedSubmissionModuleIds.includes(moduleId);
    const expandedSubmissionModuleIds = expanded
      ? learnerWorkspace.context.expandedSubmissionModuleIds.filter((id) => id !== moduleId)
      : [...learnerWorkspace.context.expandedSubmissionModuleIds, moduleId];
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        expandedSubmissionModuleIds
      }
    });
    if (!expanded) {
      const taskIds = contextModuleOptions()
        .find((module) => module.id === moduleId)
        ?.items.filter((item) => item.task?.has_submission)
        .map((item) => item.task?.id)
        .filter((taskId): taskId is string => Boolean(taskId)) ?? [];
      await Promise.all(taskIds.map((taskId) => ensureSubmissionHistoryLoaded(taskId)));
    }
  }

  function toggleContextSubmission(referenceKey: string) {
    const expanded = learnerWorkspace.context.expandedSubmissionKeys.includes(referenceKey);
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        expandedSubmissionKeys: expanded
          ? learnerWorkspace.context.expandedSubmissionKeys.filter((key) => key !== referenceKey)
          : [...learnerWorkspace.context.expandedSubmissionKeys, referenceKey]
      }
    });
  }

  async function openContextReference(referenceKey: string) {
    if (referenceKey.startsWith("submission:")) {
      await ensureSubmissionHistoryLoaded(referenceKey.slice("submission:".length));
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        compactSurface: "materials",
        readingReferenceKey: referenceKey,
        readerScrollTop: 0
      }
    });
  }

  function closeContextReader() {
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        readingReferenceKey: null
      }
    });
  }

  function rememberContextScroll(scrollTop: number) {
    if (Math.abs(learnerWorkspace.context.bookScrollTop - scrollTop) < 1) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        bookScrollTop: Math.max(0, scrollTop)
      }
    });
  }

  function rememberWorkScroll(scrollTop: number) {
    if (Math.abs(learnerWorkspace.context.workScrollTop - scrollTop) < 1) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        workScrollTop: Math.max(0, scrollTop)
      }
    });
  }

  function rememberReaderScroll(scrollTop: number) {
    if (Math.abs(learnerWorkspace.context.readerScrollTop - scrollTop) < 1) {
      return;
    }
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      context: {
        ...learnerWorkspace.context,
        readerScrollTop: Math.max(0, scrollTop)
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
    syncLearnerNavigation({
      surface: "task",
      moduleId: learnerWorkspace.activeTask.moduleId,
      taskId,
      panel: "result"
    }, "replace");
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
    const activeModuleRemainsAccessible =
      modularWorkspace.activeTab !== null && openableIds.has(modularWorkspace.activeTab);
    const requestedView = activeModuleRemainsAccessible ? "content" : "overview";
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

    // A graph refresh must not pull learners out of an active task or result.
    // Only revoked module access requires a safe navigation correction.
    if (!activeModuleRemainsAccessible && learnerWorkspace.surface !== "graph") {
      syncLearnerNavigation(
        { surface: "graph", moduleId: null, taskId: null, panel: null },
        "replace"
      );
    }
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
      modularRestoreState = "ready";
      modularRestoreMessage = null;
      restoreHistoryContext();
      return;
    }

    modularRestoreState = "failed";
    modularRestoreMessage = "Die Inhalte konnten nicht vollständig wiederhergestellt werden. Du kannst die Module im Lernpfad erneut öffnen.";
    syncLearnerNavigation(
      { surface: "graph", moduleId: null, taskId: null, panel: null },
      "replace"
    );
  }

  async function restoreOpenModulesInBackground(moduleIds: string[]) {
    const pendingIds = moduleIds.filter((moduleId) => !moduleCache[moduleId]);
    await Promise.all(pendingIds.map((moduleId) => ensureModuleLoaded(moduleId)));
    restoreHistoryContext();
  }

  function setModularWorkspaceState(next: ModularWorkspaceState) {
    modularWorkspace = next;
  }

  function setLinearWorkspaceState(next: LinearWorkspaceState) {
    linearWorkspace = next;
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

    const pendingLoad = pendingSubmissionHistoryLoads.get(taskId);
    if (pendingLoad) {
      return pendingLoad;
    }

    const load = (async () => {
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
    })();
    pendingSubmissionHistoryLoads.set(taskId, load);

    try {
      return await load;
    } finally {
      pendingSubmissionHistoryLoads.delete(taskId);
    }
  }

  async function pollFeedbackSubmission(
    taskId: string,
    submissionId: string | null,
    intent: "feedback" | "submit",
    completedMessage?: string
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
          submissionMessageState = intent === "submit" ? "submitted" : "feedback";
          feedbackPendingTaskId = null;
          feedbackStatusTaskId = taskId;
          feedbackStatusMessage = completedMessage ?? (intent === "submit" ? "Aufgabe abgegeben" : "Rückmeldung ist bereit");
          pendingSubmissionIntent = null;
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
  }) {
    const { taskId, taskKind, file } = payload;

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
      await pollFeedbackSubmission(taskId, submission.id ?? null, "feedback");
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

  async function handleProgressPersisted(taskId: string, submission?: LearningSubmission | null) {
    if (submission) {
      setTaskHistory(taskId, [
        submission,
        ...historyForTask(taskId).filter((entry) => entry.id !== submission.id)
      ]);
      void pollFeedbackSubmission(taskId, submission.id, "submit", "Rückmeldung ist bereit");
      return;
    }
    await ensureSubmissionHistoryLoaded(taskId);
    markActiveTaskResult(taskId);
    await refreshModularGraph().catch(() => undefined);
  }

  function enhanceTaskForm(taskId: string): SubmitFunction {
    return ({ submitter, cancel }) => {
      if (!(submitter instanceof HTMLButtonElement)) {
        return;
      }

      const intent = submitter.value === "feedback" ? "feedback" : "submit";
      const attempt = beginSubmissionAttempt(feedbackPendingTaskId, taskId, intent);
      if (!attempt.accepted) {
        setClientSubmissionError(taskId, attempt.statusMessage);
        cancel();
        return;
      }
      setClientSubmissionError(null, null);
      feedbackPendingTaskId = attempt.taskId;
      feedbackStatusTaskId = attempt.taskId;
      pendingSubmissionIntent = attempt.intent;
      feedbackStatusMessage = attempt.statusMessage;

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
            if (browser) {
              const draftScope = {
                learnerSub: data.user?.sub ?? null,
                courseId: data.courseId,
                taskId: payload.finalizedTaskId,
                mode: "text" as const
              };
              clearSubmissionDraft(window.sessionStorage, draftScope);
              clearSubmissionDraft(window.localStorage, draftScope);
            }
            setTaskHistory(payload.finalizedTaskId, [
              payload.finalizedSubmission,
              ...historyForTask(payload.finalizedTaskId).filter((entry) => entry.id !== payload.finalizedSubmission?.id)
            ]);
            submissionMessageState = "submitted";
            feedbackPendingTaskId = null;
            feedbackStatusTaskId = payload.finalizedTaskId;
            pendingSubmissionIntent = null;
            feedbackStatusMessage = "Aufgabe abgegeben";
            markActiveTaskResult(payload.finalizedTaskId);
            await refreshModularGraph().catch(() => undefined);
            return;
          }
          await refreshModularGraph().catch(() => undefined);
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
            (intent === "submit" ? "Die finale Abgabe konnte nicht erstellt werden." : "Die Rückmeldung konnte nicht angefordert werden.");
          return;
        }

        await applyAction(result);
      };
    };
  }

  function dismissFeedbackStatus(taskId: string) {
    if (feedbackStatusTaskId !== taskId) {
      return;
    }
    feedbackStatusTaskId = null;
    feedbackStatusMessage = null;
    if (submissionMessageState === "feedback" || submissionMessageState === "submitted") {
      submissionMessageState = null;
    }
  }

  async function openModule(moduleId: string) {
    const module = graphModuleById(moduleId);
    if (!module || (module.status !== "open" && module.status !== "done")) {
      return;
    }
    if (module.module_kind === "practice") {
      const query = new URLSearchParams({
        course_id: data.courseId,
        practice_module_id: module.id
      });
      window.location.assign(`/learning/practice?${query.toString()}`);
      return;
    }

    const selectingContext = learnerWorkspace.surface === "graph" && Boolean(learnerWorkspace.activeTask);
    const moduleAlreadyLoaded = Boolean(moduleCache[moduleId]);
    const openTabs = modularWorkspace.openTabs.includes(moduleId)
      ? modularWorkspace.openTabs
      : [...modularWorkspace.openTabs, moduleId];

    setModularWorkspaceState({
      ...modularWorkspace,
      view: "content",
      openTabs,
      activeTab: selectingContext
        ? learnerWorkspace.activeTask?.moduleId ?? modularWorkspace.activeTab
        : moduleId
    });
    modularRestoreState = "ready";
    modularRestoreMessage = null;

    const loaded = moduleAlreadyLoaded || await ensureModuleLoaded(moduleId);
    if (!loaded) {
      return;
    }

    if (selectingContext && learnerWorkspace.activeTask) {
      const firstMaterialKey = moduleContentItems(moduleCache[moduleId] ?? null)
        .find((item) => item.kind === "material")?.key;
      const task = learnerWorkspace.activeTask;
      setLearnerWorkspaceState({
        ...learnerWorkspace,
        surface: "task",
        openedModuleIds: openTabs,
        activeTask: learnerWorkspace.activeTask,
        context: {
          ...learnerWorkspace.context,
          compactSurface: "materials",
          expandedContextModuleIds: [
            ...learnerWorkspace.context.expandedContextModuleIds.filter((id) => id !== moduleId),
            moduleId
          ],
          expandedModuleMaterialKeys: {
            ...learnerWorkspace.context.expandedModuleMaterialKeys,
            [moduleId]: firstMaterialKey ? [firstMaterialKey] : []
          },
          focusedModuleId: moduleId
        }
      });
      syncLearnerNavigation(
        {
          surface: "task",
          moduleId: task.moduleId,
          taskId: task.taskId,
          panel: task.status === "result" ? "result" : null
        },
        "replace"
      );
      return;
    }

    setLearnerWorkspaceState({
      ...learnerWorkspace,
      surface: "reading",
      openedModuleIds: openTabs,
      activeTask: null
    });
    syncLearnerNavigation({ surface: "reading", moduleId, taskId: null, panel: null }, "push");
  }

  function clearClosedModuleUndo() {
    if (closedModuleUndoTimer !== null && browser) {
      window.clearTimeout(closedModuleUndoTimer);
    }
    closedModuleUndoTimer = null;
    closedModuleSnapshot = null;
  }

  function removeOpenModule(moduleId: string) {
    if (learnerWorkspace.activeTask?.moduleId === moduleId) {
      return;
    }
    const currentIndex = modularWorkspace.openTabs.indexOf(moduleId);
    if (currentIndex < 0) {
      return;
    }

    const module = graphModuleById(moduleId);
    const moduleItems = moduleContentItems(moduleCache[moduleId] ?? null);
    const moduleReferenceKeys = new Set([
      ...moduleItems.filter((item) => item.kind === "material").map((item) => item.key),
      ...moduleItems.filter((item) => item.task).map((item) => `submission:${item.task?.id}`)
    ]);
    clearClosedModuleUndo();
    closedModuleSnapshot = {
      moduleId,
      title: module?.title ?? "Modul",
      index: currentIndex,
      previousActiveTab: modularWorkspace.activeTab,
      expanded: learnerWorkspace.context.expandedContextModuleIds.includes(moduleId),
      expandedMaterialKeys: learnerWorkspace.context.expandedModuleMaterialKeys[moduleId] ?? null,
      submissionsExpanded: learnerWorkspace.context.expandedSubmissionModuleIds.includes(moduleId),
      expandedSubmissionKeys: learnerWorkspace.context.expandedSubmissionKeys.filter((key) =>
        moduleReferenceKeys.has(key)
      ),
      readingReferenceKey:
        learnerWorkspace.context.readingReferenceKey && moduleReferenceKeys.has(learnerWorkspace.context.readingReferenceKey)
          ? learnerWorkspace.context.readingReferenceKey
          : null
    };
    if (browser) {
      closedModuleUndoTimer = window.setTimeout(() => clearClosedModuleUndo(), 8000);
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
    const expandedModuleMaterialKeys = { ...learnerWorkspace.context.expandedModuleMaterialKeys };
    delete expandedModuleMaterialKeys[moduleId];
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      openedModuleIds: remaining,
      context: {
        ...learnerWorkspace.context,
        expandedContextModuleIds: learnerWorkspace.context.expandedContextModuleIds.filter((id) => id !== moduleId),
        expandedModuleMaterialKeys,
        expandedSubmissionModuleIds: learnerWorkspace.context.expandedSubmissionModuleIds.filter((id) => id !== moduleId),
        expandedSubmissionKeys: learnerWorkspace.context.expandedSubmissionKeys.filter((key) => !moduleReferenceKeys.has(key)),
        readingReferenceKey:
          learnerWorkspace.context.readingReferenceKey && moduleReferenceKeys.has(learnerWorkspace.context.readingReferenceKey)
            ? null
            : learnerWorkspace.context.readingReferenceKey,
        focusedModuleId: learnerWorkspace.context.focusedModuleId === moduleId ? null : learnerWorkspace.context.focusedModuleId
      }
    });
    if (learnerWorkspace.surface !== "task") {
      syncLearnerNavigation(
        nextActive
          ? { surface: "reading", moduleId: nextActive, taskId: null, panel: null }
          : { surface: "graph", moduleId: null, taskId: null, panel: null },
        "replace"
      );
    }
  }

  function undoCloseModule() {
    const snapshot = closedModuleSnapshot;
    if (!snapshot || !openableModuleIds().has(snapshot.moduleId)) return;
    const openTabs = [...modularWorkspace.openTabs];
    openTabs.splice(Math.min(snapshot.index, openTabs.length), 0, snapshot.moduleId);
    setModularWorkspaceState({
      ...modularWorkspace,
      openTabs,
      activeTab:
        snapshot.previousActiveTab && openTabs.includes(snapshot.previousActiveTab)
          ? snapshot.previousActiveTab
          : modularWorkspace.activeTab ?? snapshot.moduleId
    });
    setLearnerWorkspaceState({
      ...learnerWorkspace,
      openedModuleIds: openTabs,
      context: {
        ...learnerWorkspace.context,
        expandedContextModuleIds: snapshot.expanded
          ? [...new Set([...learnerWorkspace.context.expandedContextModuleIds, snapshot.moduleId])]
          : learnerWorkspace.context.expandedContextModuleIds,
        expandedModuleMaterialKeys: snapshot.expandedMaterialKeys
          ? {
              ...learnerWorkspace.context.expandedModuleMaterialKeys,
              [snapshot.moduleId]: snapshot.expandedMaterialKeys
            }
          : learnerWorkspace.context.expandedModuleMaterialKeys,
        expandedSubmissionModuleIds: snapshot.submissionsExpanded
          ? [...new Set([...learnerWorkspace.context.expandedSubmissionModuleIds, snapshot.moduleId])]
          : learnerWorkspace.context.expandedSubmissionModuleIds,
        expandedSubmissionKeys: [
          ...new Set([...learnerWorkspace.context.expandedSubmissionKeys, ...snapshot.expandedSubmissionKeys])
        ],
        readingReferenceKey: snapshot.readingReferenceKey,
        focusedModuleId: snapshot.moduleId
      }
    });
    void ensureModuleLoaded(snapshot.moduleId);
    clearClosedModuleUndo();
  }

  function updateLayoutPreferences(next: Partial<LayoutPreferences>) {
    layoutPreferences = {
      ...layoutPreferences,
      ...next
    };
  }

  function applyFontScale(value: number) {
    workspaceRoot?.style.setProperty("--learning-unit-font-scale", String(value));
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

  function previewTaskColumnRatio(value: number) {
    taskColumnRatio = value;
  }

  function commitTaskColumnRatio(value: number) {
    taskColumnRatio = value;
    if (browser) {
      writeTaskColumnRatio(window.localStorage, data.user?.sub ?? null, value);
    }
  }

  function resetLayoutPreferences() {
    const viewportWidth = currentViewportWidth();
    const layoutDefaults = defaultLayoutPreferences(viewportWidth);
    const chromeDefaults = defaultWorkspaceChrome(viewportWidth);

    layoutPreferences = layoutDefaults;
    taskColumnRatio = null;
    applyFontScale(layoutDefaults.fontScale);
    removeTaskColumnRatio(window.localStorage, data.user?.sub ?? null);
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
        tocOpen: chromeDefaults.tocOpen
      });
      return;
    }

    setLinearWorkspaceState({
      ...linearWorkspace,
      tocOpen: chromeDefaults.tocOpen
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
    void ensureSubmissionHistoryLoaded(data.historyTaskId);
  }

  onMount(() => {
    const viewportWidth = currentViewportWidth();
    graphState = data.graph ? plainGraph(data.graph) : null;
    taskColumnRatio = readTaskColumnRatio(window.localStorage, data.user?.sub ?? null);

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
      accessibleContextModuleIds: isModularUnit()
        ? undefined
        : new Set(data.sections.map((section) => section.section.id)),
      accessibleTaskKeys: isModularUnit()
        ? undefined
        : new Set(currentContentItems().filter((item) => item.kind === "task").map((item) => item.key)),
      accessibleReferenceKeys: isModularUnit()
        ? undefined
        : new Set(
            currentContentItems().flatMap((item) => {
              if (item.kind === "material") return [item.key];
              if (item.task?.has_submission) return [`submission:${item.task.id}`];
              return [];
            })
          )
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
      const directTaskRequested = Boolean(data.requestedTaskId && data.activeModule);
      if (seeded.view === "content" && seeded.openTabs.length > 0) {
        if (directTaskRequested) {
          modularRestoreState = "ready";
          void restoreOpenModulesInBackground(seeded.openTabs);
        } else {
          void restoreOpenModules(seeded.openTabs);
        }
      } else {
        modularRestoreState = "idle";
      }
    } else {
      setLinearWorkspaceState({
        ...defaultLinearWorkspaceState(viewportWidth),
        tocOpen: stored.preferences.navigationVisible
      });
    }

    applyFontScale(layoutPreferences.fontScale);
    workspaceReady = true;
    if (!isModularUnit()) {
      restoreHistoryContext();
    }
    void restoreSurfaceFromUrl();
    const handlePopState = () => void restoreSurfaceFromUrl();
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  });

  $effect(() => {
    graphState = data.graph ? plainGraph(data.graph) : null;
  });

  $effect(() => {
    const historyTaskId = data.historyTaskId;
    const history = data.history;
    const message = data.message;
    untrack(() => {
      if (historyTaskId) {
        setTaskHistory(historyTaskId, history);
      }
      submissionMessageState = message;
    });
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
        surface: isModularUnit() && !learnerWorkspace.openedModuleIds.length ? "graph" : "reading",
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
    <div class="learning-unit-flash"><StatusMessage tone="success" title="Abgabe gespeichert" /></div>
  {/if}

  {#if modularRestoreMessage}
    <div class="learning-unit-flash"><StatusMessage tone="error" title="Lernraum nicht wiederhergestellt" description={modularRestoreMessage} /></div>
  {/if}

  {#if form?.message}
    <div class="learning-unit-flash"><StatusMessage tone="error" title="Aktion nicht abgeschlossen" description={form.message} focusOnMount={true} /></div>
  {/if}

  {#if isModularUnit()}
    <section class="learning-unit-toolbar">
      <div class="learning-unit-layout-frame learning-unit-layout-frame--toolbar">
        <div class="learning-unit-toolbar__main">
          <div class="learning-unit-toolbar__leading">
            {#if learnerWorkspace.surface !== "graph"}
              <button class="learner-path-back" type="button" onclick={showLearningPath}>← Zum Lernpfad</button>
            {:else}
              <p class="workspace-label">Lernpfad</p>
            {/if}
          </div>

          {#if learnerWorkspace.surface !== "graph"}
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

    {#if learnerWorkspace.surface === "graph"}
      <LearningUnitOverview graph={graphState} nodes={flowNodes} edges={flowEdges} />
    {/if}

    <div hidden={learnerWorkspace.surface === "graph"} class="learning-unit-mounted-workspace">
      <div class="learning-unit-layout-rail">
        <div class="learning-unit-layout-frame">
          <section class="learning-unit-stage learning-unit-stage--content">
            {#if modularRestoreState === "restoring"}
              <section class="workspace-panel learning-unit-empty-state">
                <p class="learning-unit-empty-copy">Inhalte werden wiederhergestellt …</p>
              </section>
            {:else if modularRestoreState === "failed"}
              <section class="workspace-panel learning-unit-empty-state">
                <p class="learning-unit-empty-copy">Der Lernraum wechselt zurück zum Lernpfad.</p>
              </section>
            {:else if modularWorkspace.activeTab && moduleErrors[modularWorkspace.activeTab]}
              <section class="workspace-panel learning-unit-empty-state">
                <StatusMessage
                  tone="error"
                  title="Modul nicht geladen"
                  description={moduleErrors[modularWorkspace.activeTab]}
                  actionLabel="Erneut versuchen"
                  onAction={() => {
                    if (modularWorkspace.activeTab) {
                      void ensureModuleLoaded(modularWorkspace.activeTab);
                    }
                  }}
                />
              </section>
            {:else}
              <LearnerContentWorkspace
                learnerSub={data.user?.sub ?? null}
                courseId={data.courseId}
                unitTitle={data.selectedUnit?.unit.title ?? "Lerneinheit"}
                unitType="modular"
                contentGroups={contentGroups()}
                mode={learnerWorkspace.surface === "task" || (learnerWorkspace.surface === "graph" && learnerWorkspace.activeTask) ? "working" : "orienting"}
                activeTaskKey={learnerWorkspace.activeTask?.itemKey ?? null}
                activeEditorMode={learnerWorkspace.activeTask?.editorMode ?? null}
                workStatus={learnerWorkspace.activeTask?.status ?? "editing"}
                compactSurface={learnerWorkspace.context.compactSurface}
                navigationVisible={learnerWorkspace.preferences.navigationVisible}
                collapsedItemKeys={learnerWorkspace.collapsedItemKeys}
                contextModules={contextModuleOptions()}
                expandedModuleMaterialKeys={learnerWorkspace.context.expandedModuleMaterialKeys}
                expandedContextModuleIds={learnerWorkspace.context.expandedContextModuleIds}
                expandedSubmissionModuleIds={learnerWorkspace.context.expandedSubmissionModuleIds}
                expandedSubmissionKeys={learnerWorkspace.context.expandedSubmissionKeys}
                focusedContextModuleId={learnerWorkspace.context.focusedModuleId}
                closedContextModuleTitle={closedModuleSnapshot?.title ?? null}
                readingReferenceKey={learnerWorkspace.context.readingReferenceKey}
                contextScrollTop={learnerWorkspace.context.bookScrollTop}
                workScrollTop={learnerWorkspace.context.workScrollTop}
                readerScrollTop={learnerWorkspace.context.readerScrollTop}
                taskColumnRatio={taskColumnRatio}
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
                enhanceTaskForm={enhanceTaskForm}
                onSubmitUploadFeedback={submitUploadFeedback}
                onBeginTask={beginTaskWorkspace}
                onPauseTask={leaveTaskWorkspace}
                onCloseModule={removeOpenModule}
                onSetCompactSurface={setCompactSurface}
                onToggleMaterial={toggleReadingMaterial}
                onToggleContextModuleMaterial={toggleContextModuleMaterial}
                onToggleContextModule={toggleContextModule}
                onToggleContextSubmissions={toggleContextSubmissions}
                onToggleContextSubmission={toggleContextSubmission}
                onOpenContextReference={openContextReference}
                onCloseContextReader={closeContextReader}
                onUndoCloseModule={undoCloseModule}
                onContextScroll={rememberContextScroll}
                onWorkScroll={rememberWorkScroll}
                onReaderScroll={rememberReaderScroll}
                onPreviewTaskColumnRatio={previewTaskColumnRatio}
                onCommitTaskColumnRatio={commitTaskColumnRatio}
                onDismissFeedbackStatus={dismissFeedbackStatus}
                onProgressPersisted={handleProgressPersisted}
              />
            {/if}
          </section>
        </div>
      </div>
    </div>
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
            mode={learnerWorkspace.surface === "task" ? "working" : "orienting"}
            activeTaskKey={learnerWorkspace.activeTask?.itemKey ?? null}
            activeEditorMode={learnerWorkspace.activeTask?.editorMode ?? null}
            workStatus={learnerWorkspace.activeTask?.status ?? "editing"}
            compactSurface={learnerWorkspace.context.compactSurface}
            navigationVisible={learnerWorkspace.preferences.navigationVisible}
            collapsedItemKeys={learnerWorkspace.collapsedItemKeys}
            contextModules={contextModuleOptions()}
            expandedModuleMaterialKeys={learnerWorkspace.context.expandedModuleMaterialKeys}
            expandedContextModuleIds={learnerWorkspace.context.expandedContextModuleIds}
            expandedSubmissionModuleIds={learnerWorkspace.context.expandedSubmissionModuleIds}
            expandedSubmissionKeys={learnerWorkspace.context.expandedSubmissionKeys}
            focusedContextModuleId={learnerWorkspace.context.focusedModuleId}
            readingReferenceKey={learnerWorkspace.context.readingReferenceKey}
            contextScrollTop={learnerWorkspace.context.bookScrollTop}
            workScrollTop={learnerWorkspace.context.workScrollTop}
            readerScrollTop={learnerWorkspace.context.readerScrollTop}
            taskColumnRatio={taskColumnRatio}
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
            enhanceTaskForm={enhanceTaskForm}
            onSubmitUploadFeedback={submitUploadFeedback}
            onBeginTask={beginTaskWorkspace}
            onPauseTask={leaveTaskWorkspace}
            onCloseModule={() => {}}
            onSetCompactSurface={setCompactSurface}
            onToggleMaterial={toggleReadingMaterial}
            onToggleContextModuleMaterial={toggleContextModuleMaterial}
            onToggleContextModule={toggleContextModule}
            onToggleContextSubmissions={toggleContextSubmissions}
            onToggleContextSubmission={toggleContextSubmission}
            onOpenContextReference={openContextReference}
            onCloseContextReader={closeContextReader}
            onContextScroll={rememberContextScroll}
            onWorkScroll={rememberWorkScroll}
            onReaderScroll={rememberReaderScroll}
            onPreviewTaskColumnRatio={previewTaskColumnRatio}
            onCommitTaskColumnRatio={commitTaskColumnRatio}
            onDismissFeedbackStatus={dismissFeedbackStatus}
            onProgressPersisted={handleProgressPersisted}
          />
        </section>
      </div>
    </div>
  {/if}
</div>
