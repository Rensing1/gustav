export const LEARNER_WORKSPACE_STORAGE_VERSION = 5;

export type LearnerWorkspaceSurface = "graph" | "reading" | "task";
export type LearnerWorkStatus = "editing" | "result";
export type LearnerEditorMode = "text" | "upload" | null;
export type LearnerCompactSurface = "task" | "materials";
export type LearnerFontSize = "small" | "standard" | "large";

export type LearnerActiveTask = {
  itemKey: string;
  taskId: string;
  moduleId: string | null;
  status: LearnerWorkStatus;
  editorMode: LearnerEditorMode;
};

export type LearnerWorkspaceState = {
  surface: LearnerWorkspaceSurface;
  openedModuleIds: string[];
  collapsedItemKeys: string[];
  activeTask: LearnerActiveTask | null;
  context: {
    compactSurface: LearnerCompactSurface;
    expandedContextModuleIds: string[];
    expandedModuleMaterialKeys: Record<string, string[]>;
    expandedSubmissionModuleIds: string[];
    expandedSubmissionKeys: string[];
    readingReferenceKey: string | null;
    focusedModuleId: string | null;
    bookScrollTop: number;
    workScrollTop: number;
    readerScrollTop: number;
  };
  returnPosition: {
    moduleId: string | null;
    scrollY: number;
    focusId: string | null;
  } | null;
  preferences: {
    navigationVisible: boolean;
    fontSize: LearnerFontSize;
  };
};

type ReadableStorage = {
  getItem?: (key: string) => string | null;
  get?: (key: string) => string | undefined;
};

type WorkspaceAccess = {
  openableModuleIds: Set<string>;
  accessibleContextModuleIds?: Set<string>;
  accessibleTaskKeys?: Set<string>;
  accessibleReferenceKeys?: Set<string>;
};

export function defaultLearnerWorkspaceState(): LearnerWorkspaceState {
  return {
    surface: "reading",
    openedModuleIds: [],
    collapsedItemKeys: [],
    activeTask: null,
    context: {
      compactSurface: "task",
      expandedContextModuleIds: [],
      expandedModuleMaterialKeys: {},
      expandedSubmissionModuleIds: [],
      expandedSubmissionKeys: [],
      readingReferenceKey: null,
      focusedModuleId: null,
      bookScrollTop: 0,
      workScrollTop: 0,
      readerScrollTop: 0
    },
    returnPosition: null,
    preferences: {
      navigationVisible: true,
      fontSize: "standard"
    }
  };
}

/**
 * Returns the state used when a learner leaves the task surface for the graph.
 * The graph never owns a task workspace: browser drafts remain in their own
 * task-scoped storage and are restored only through the regular task entry.
 */
export function learningPathState(state: LearnerWorkspaceState): LearnerWorkspaceState {
  return {
    ...state,
    surface: "graph",
    activeTask: null
  };
}

export function learnerWorkspaceStorageKeys(
  learnerSub: string | null,
  courseId: string,
  unitId: string
): { persistent: string; tab: string } | null {
  if (!learnerSub) {
    return null;
  }

  const base = `gustav.learning.workspace:${encodeURIComponent(learnerSub)}:${courseId}:${unitId}`;
  return { persistent: base, tab: `${base}:tab` };
}

function safeString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 && value.length <= 500 ? value : null;
}

function uniqueStrings(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return [...new Set(value.map(safeString).filter((entry): entry is string => Boolean(entry)))];
}

function normalizeExpandedModuleMaterialKeys(
  value: unknown,
  openedModuleIds: Set<string>,
  access: WorkspaceAccess
): Record<string, string[]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  const normalized: Record<string, string[]> = {};
  for (const [moduleId, rawKeys] of Object.entries(value)) {
    if (!openedModuleIds.has(moduleId) || !Array.isArray(rawKeys)) {
      continue;
    }
    normalized[moduleId] = uniqueStrings(rawKeys).filter(
      (key) => !access.accessibleReferenceKeys || access.accessibleReferenceKeys.has(key)
    );
  }
  return normalized;
}

function safeScrollTop(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, value) : 0;
}

function normalizeActiveTask(value: unknown): LearnerActiveTask | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Partial<LearnerActiveTask>;
  const itemKey = safeString(candidate.itemKey);
  const taskId = safeString(candidate.taskId);
  if (!itemKey || !taskId) {
    return null;
  }
  return {
    itemKey,
    taskId,
    moduleId: safeString(candidate.moduleId),
    status: candidate.status === "result" ? "result" : "editing",
    editorMode: candidate.editorMode === "text" || candidate.editorMode === "upload" ? candidate.editorMode : null
  };
}

export function normalizeLearnerWorkspaceState(
  raw: unknown,
  access: WorkspaceAccess
): LearnerWorkspaceState {
  const defaults = defaultLearnerWorkspaceState();
  const candidate = raw && typeof raw === "object" ? (raw as Partial<LearnerWorkspaceState>) : {};
  const rawContext: Partial<LearnerWorkspaceState["context"]> =
    candidate.context && typeof candidate.context === "object" ? candidate.context : {};
  const rawPreferences: Partial<LearnerWorkspaceState["preferences"]> =
    candidate.preferences && typeof candidate.preferences === "object" ? candidate.preferences : {};
  const rawReturn: Partial<NonNullable<LearnerWorkspaceState["returnPosition"]>> | null =
    candidate.returnPosition && typeof candidate.returnPosition === "object"
    ? candidate.returnPosition
    : null;

  const openedModuleIds = uniqueStrings(candidate.openedModuleIds).filter((id) => access.openableModuleIds.has(id));
  const openedModuleIdSet = new Set(openedModuleIds);
  const contextModuleIdSet = access.accessibleContextModuleIds ?? openedModuleIdSet;
  const expandedContextModuleIds = uniqueStrings(rawContext.expandedContextModuleIds).filter((id) =>
    contextModuleIdSet.has(id)
  );
  const expandedSubmissionModuleIds = uniqueStrings(rawContext.expandedSubmissionModuleIds).filter((id) =>
    contextModuleIdSet.has(id)
  );
  const expandedSubmissionKeys = uniqueStrings(rawContext.expandedSubmissionKeys).filter((key) =>
    !access.accessibleReferenceKeys || access.accessibleReferenceKeys.has(key)
  );

  let activeTask = normalizeActiveTask(candidate.activeTask);
  if (
    activeTask &&
    ((activeTask.moduleId && !access.openableModuleIds.has(activeTask.moduleId)) ||
      (access.accessibleTaskKeys && !access.accessibleTaskKeys.has(activeTask.itemKey)))
  ) {
    activeTask = null;
  }

  const readingCandidate = safeString(rawContext.readingReferenceKey);
  const legacyMode = (candidate as Partial<LearnerWorkspaceState> & { mode?: unknown }).mode;
  const requestedSurface = candidate.surface ?? (legacyMode === "working" ? "task" : "reading");
  if (requestedSurface === "graph") {
    activeTask = null;
  }
  const surface: LearnerWorkspaceSurface = requestedSurface === "task" && activeTask
    ? "task"
    : requestedSurface === "graph"
      ? "graph"
      : "reading";
  const fontSize: LearnerFontSize =
    rawPreferences.fontSize === "small" || rawPreferences.fontSize === "large"
      ? rawPreferences.fontSize
      : "standard";

  return {
    surface,
    openedModuleIds,
    collapsedItemKeys: uniqueStrings(candidate.collapsedItemKeys),
    activeTask,
    context: {
      compactSurface: rawContext.compactSurface === "materials" ? "materials" : "task",
      expandedContextModuleIds,
      expandedModuleMaterialKeys: normalizeExpandedModuleMaterialKeys(
        rawContext.expandedModuleMaterialKeys,
        contextModuleIdSet,
        access
      ),
      expandedSubmissionModuleIds,
      expandedSubmissionKeys,
      readingReferenceKey:
        readingCandidate && (!access.accessibleReferenceKeys || access.accessibleReferenceKeys.has(readingCandidate))
          ? readingCandidate
          : null,
      focusedModuleId:
        safeString(rawContext.focusedModuleId) && contextModuleIdSet.has(safeString(rawContext.focusedModuleId) as string)
          ? safeString(rawContext.focusedModuleId)
          : null,
      bookScrollTop: safeScrollTop(
        rawContext.bookScrollTop ?? (rawContext as { scrollTop?: unknown }).scrollTop
      ),
      workScrollTop: safeScrollTop(rawContext.workScrollTop),
      readerScrollTop: safeScrollTop(rawContext.readerScrollTop)
    },
    returnPosition: rawReturn
      ? {
          moduleId: safeString(rawReturn.moduleId),
          scrollY:
            typeof rawReturn.scrollY === "number" && Number.isFinite(rawReturn.scrollY)
              ? Math.max(0, rawReturn.scrollY)
              : 0,
          focusId: safeString(rawReturn.focusId)
        }
      : null,
    preferences: {
      navigationVisible:
        typeof rawPreferences.navigationVisible === "boolean"
          ? rawPreferences.navigationVisible
          : defaults.preferences.navigationVisible,
      fontSize
    }
  };
}

function storageGet(storage: ReadableStorage | null, key: string): string | null {
  if (!storage) {
    return null;
  }
  if (typeof storage.getItem === "function") {
    return storage.getItem(key);
  }
  return storage.get?.(key) ?? null;
}

function parseVersioned(storage: ReadableStorage | null, key: string): Record<string, unknown> {
  const value = storageGet(storage, key);
  if (!value) {
    return {};
  }
  try {
    const parsed = JSON.parse(value) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      ((parsed as { version?: unknown }).version === LEARNER_WORKSPACE_STORAGE_VERSION ||
        (parsed as { version?: unknown }).version === 4 ||
        (parsed as { version?: unknown }).version === 3 ||
        (parsed as { version?: unknown }).version === 2 ||
        (parsed as { version?: unknown }).version === 1)
    ) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Invalid browser state must never prevent the learner from opening the unit.
  }
  return {};
}

export function readLearnerWorkspaceState({
  localStorage,
  sessionStorage,
  learnerSub,
  courseId,
  unitId,
  openableModuleIds,
  accessibleContextModuleIds,
  accessibleTaskKeys,
  accessibleReferenceKeys
}: {
  localStorage: ReadableStorage | null;
  sessionStorage: ReadableStorage | null;
  learnerSub: string | null;
  courseId: string;
  unitId: string;
  openableModuleIds: Set<string>;
  accessibleContextModuleIds?: Set<string>;
  accessibleTaskKeys?: Set<string>;
  accessibleReferenceKeys?: Set<string>;
}): LearnerWorkspaceState {
  const keys = learnerWorkspaceStorageKeys(learnerSub, courseId, unitId);
  if (!keys) {
    return defaultLearnerWorkspaceState();
  }

  const persistent = parseVersioned(localStorage, keys.persistent);
  const tab = parseVersioned(sessionStorage, keys.tab);
  const tabContext = tab.context && typeof tab.context === "object" ? tab.context : {};
  const tabVersion = (tab as { version?: unknown }).version;

  return normalizeLearnerWorkspaceState(
    {
      surface: tab.surface,
      mode: tab.mode,
      openedModuleIds: persistent.openedModuleIds,
      collapsedItemKeys: tab.collapsedItemKeys,
      activeTask: tab.activeTask,
      returnPosition: tab.returnPosition,
      preferences: persistent.preferences,
      context: {
        ...tabContext,
        // Version 4 used this array for the source picker. Opened modules are
        // now the only context source, so the old picker expansion is ignored.
        expandedContextModuleIds:
          tabVersion === LEARNER_WORKSPACE_STORAGE_VERSION
            ? (tabContext as { expandedContextModuleIds?: unknown }).expandedContextModuleIds
            : [],
        expandedSubmissionModuleIds:
          tabVersion === LEARNER_WORKSPACE_STORAGE_VERSION
            ? (tabContext as { expandedSubmissionModuleIds?: unknown }).expandedSubmissionModuleIds
            : [],
        expandedSubmissionKeys:
          tabVersion === LEARNER_WORKSPACE_STORAGE_VERSION
            ? (tabContext as { expandedSubmissionKeys?: unknown }).expandedSubmissionKeys
            : [],
        // Version 2 opened its narrow reader automatically. Do not revive that
        // obsolete presentation as a deliberate full-width reading choice.
        readingReferenceKey:
          tabVersion === 2
            ? null
            : (tabContext as { readingReferenceKey?: unknown }).readingReferenceKey
      }
    },
    { openableModuleIds, accessibleContextModuleIds, accessibleTaskKeys, accessibleReferenceKeys }
  );
}

export function serializeLearnerWorkspacePersistentState(state: LearnerWorkspaceState): string {
  return JSON.stringify({
    version: LEARNER_WORKSPACE_STORAGE_VERSION,
    openedModuleIds: state.openedModuleIds,
    preferences: state.preferences
  });
}

export function serializeLearnerWorkspaceTabState(state: LearnerWorkspaceState): string {
  return JSON.stringify({
    version: LEARNER_WORKSPACE_STORAGE_VERSION,
    surface: state.surface,
    collapsedItemKeys: state.collapsedItemKeys,
    activeTask: state.activeTask,
    context: {
      compactSurface: state.context.compactSurface,
      expandedContextModuleIds: state.context.expandedContextModuleIds,
      expandedModuleMaterialKeys: state.context.expandedModuleMaterialKeys,
      expandedSubmissionModuleIds: state.context.expandedSubmissionModuleIds,
      expandedSubmissionKeys: state.context.expandedSubmissionKeys,
      readingReferenceKey: state.context.readingReferenceKey,
      focusedModuleId: state.context.focusedModuleId,
      bookScrollTop: state.context.bookScrollTop,
      workScrollTop: state.context.workScrollTop,
      readerScrollTop: state.context.readerScrollTop
    },
    returnPosition: state.returnPosition
  });
}
