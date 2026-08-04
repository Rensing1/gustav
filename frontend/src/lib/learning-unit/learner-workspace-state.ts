export const LEARNER_WORKSPACE_STORAGE_VERSION = 2;

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

export type LearnerContextReference = {
  key: string;
  kind: "material" | "submission";
  id: string;
  moduleId: string | null;
  taskId: string | null;
};

export type LearnerWorkspaceState = {
  surface: LearnerWorkspaceSurface;
  openedModuleIds: string[];
  collapsedItemKeys: string[];
  activeTask: LearnerActiveTask | null;
  context: {
    compactSurface: LearnerCompactSurface;
    manualReferences: LearnerContextReference[];
    expandedReferenceKeys: string[];
    pickerOpen: boolean;
    expandedModuleIds: string[];
    readingReferenceKey: string | null;
    scrollTop: number;
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
      manualReferences: [],
      expandedReferenceKeys: [],
      pickerOpen: false,
      expandedModuleIds: [],
      readingReferenceKey: null,
      scrollTop: 0
    },
    returnPosition: null,
    preferences: {
      navigationVisible: true,
      fontSize: "standard"
    }
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

function normalizeReference(value: unknown): LearnerContextReference | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Partial<LearnerContextReference>;
  const key = safeString(candidate.key);
  const id = safeString(candidate.id);
  if (!key || !id || (candidate.kind !== "material" && candidate.kind !== "submission")) {
    return null;
  }
  return {
    key,
    kind: candidate.kind,
    id,
    moduleId: safeString(candidate.moduleId),
    taskId: safeString(candidate.taskId)
  };
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
  const manualReferences = (Array.isArray(rawContext.manualReferences) ? rawContext.manualReferences : [])
    .map(normalizeReference)
    .filter((entry): entry is LearnerContextReference => Boolean(entry))
    .filter((entry) => !entry.moduleId || access.openableModuleIds.has(entry.moduleId))
    .filter((entry) => !access.accessibleReferenceKeys || access.accessibleReferenceKeys.has(entry.key));
  const referenceKeys = new Set([
    ...manualReferences.map((entry) => entry.key),
    ...(access.accessibleReferenceKeys ?? [])
  ]);
  const expandedReferenceKeys = uniqueStrings(rawContext.expandedReferenceKeys).filter((key) =>
    referenceKeys.has(key)
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
      manualReferences,
      expandedReferenceKeys,
      pickerOpen: rawContext.pickerOpen === true,
      expandedModuleIds: uniqueStrings(rawContext.expandedModuleIds).filter((id) =>
        access.openableModuleIds.has(id)
      ),
      readingReferenceKey: readingCandidate && referenceKeys.has(readingCandidate) ? readingCandidate : null,
      scrollTop:
        typeof rawContext.scrollTop === "number" && Number.isFinite(rawContext.scrollTop)
          ? Math.max(0, rawContext.scrollTop)
          : 0
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
  accessibleTaskKeys,
  accessibleReferenceKeys
}: {
  localStorage: ReadableStorage | null;
  sessionStorage: ReadableStorage | null;
  learnerSub: string | null;
  courseId: string;
  unitId: string;
  openableModuleIds: Set<string>;
  accessibleTaskKeys?: Set<string>;
  accessibleReferenceKeys?: Set<string>;
}): LearnerWorkspaceState {
  const keys = learnerWorkspaceStorageKeys(learnerSub, courseId, unitId);
  if (!keys) {
    return defaultLearnerWorkspaceState();
  }

  const persistent = parseVersioned(localStorage, keys.persistent);
  const tab = parseVersioned(sessionStorage, keys.tab);
  const persistentContext =
    persistent.context && typeof persistent.context === "object" ? persistent.context : {};
  const tabContext = tab.context && typeof tab.context === "object" ? tab.context : {};

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
        ...persistentContext,
        ...tabContext,
        manualReferences: (persistentContext as { manualReferences?: unknown }).manualReferences
      }
    },
    { openableModuleIds, accessibleTaskKeys, accessibleReferenceKeys }
  );
}

export function serializeLearnerWorkspacePersistentState(state: LearnerWorkspaceState): string {
  return JSON.stringify({
    version: LEARNER_WORKSPACE_STORAGE_VERSION,
    openedModuleIds: state.openedModuleIds,
    preferences: state.preferences,
    context: {
      manualReferences: state.context.manualReferences
    }
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
      expandedReferenceKeys: state.context.expandedReferenceKeys,
      pickerOpen: state.context.pickerOpen,
      expandedModuleIds: state.context.expandedModuleIds,
      readingReferenceKey: state.context.readingReferenceKey,
      scrollTop: state.context.scrollTop
    },
    returnPosition: state.returnPosition
  });
}
