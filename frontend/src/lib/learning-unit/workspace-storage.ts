import {
  defaultLayoutPreferences,
  defaultLinearWorkspaceState,
  defaultModularWorkspaceState,
  normalizeLayoutPreferences,
  normalizeLinearWorkspaceState,
  normalizeModularWorkspaceState,
  type LayoutPreferences,
  type LinearWorkspaceState,
  type ModularWorkspaceState
} from "./layout";

export const LEARNING_UNIT_WORKSPACE_STORAGE_VERSION = 16;

type VersionedStoredWorkspaceState = {
  version: 11 | 12 | 13 | 14 | 15 | typeof LEARNING_UNIT_WORKSPACE_STORAGE_VERSION;
  modular?: Partial<ModularWorkspaceState>;
  linear?: Partial<LinearWorkspaceState>;
  layout?: Partial<LayoutPreferences>;
};

type ReadableStorage = {
  getItem?: (key: string) => string | null;
  get?: (key: string) => string | undefined;
};

export type RestoredLearningUnitWorkspaceState = {
  modular: ModularWorkspaceState;
  linear: LinearWorkspaceState;
  layout: LayoutPreferences;
};

export function learningUnitWorkspaceStorageKey(courseId: string, unitId: string): string {
  return `gustav.learning.unit-workspace:${courseId}:${unitId}`;
}

function defaultRestoredState(viewportWidth: number): RestoredLearningUnitWorkspaceState {
  return {
    modular: defaultModularWorkspaceState(viewportWidth),
    linear: defaultLinearWorkspaceState(viewportWidth),
    layout: defaultLayoutPreferences(viewportWidth)
  };
}

function storageGet(storage: ReadableStorage, key: string): string | null {
  if (typeof storage.getItem === "function") {
    return storage.getItem(key);
  }
  if (typeof storage.get === "function") {
    return storage.get(key) ?? null;
  }
  return null;
}

function isVersionedStoredWorkspaceState(value: unknown): value is VersionedStoredWorkspaceState {
  if (!value || typeof value !== "object") {
    return false;
  }

  const version = (value as { version?: unknown }).version;
  return (
    (version === 11 || version === 12 || version === 13 || version === 14 || version === 15 || version === 16) &&
    ("modular" in value || "linear" in value)
  );
}

export function readLearningUnitWorkspaceState({
  storage,
  courseId,
  unitId,
  viewportWidth,
  openableModuleIds
}: {
  storage: ReadableStorage | null;
  courseId: string;
  unitId: string;
  viewportWidth: number;
  openableModuleIds: Set<string>;
}): RestoredLearningUnitWorkspaceState {
  if (!storage) {
    return defaultRestoredState(viewportWidth);
  }

  try {
    const raw = storageGet(storage, learningUnitWorkspaceStorageKey(courseId, unitId));
    if (!raw) {
      return defaultRestoredState(viewportWidth);
    }

    const parsed = JSON.parse(raw) as unknown;
    if (isVersionedStoredWorkspaceState(parsed)) {
      return {
        modular: normalizeModularWorkspaceState(parsed.modular ?? null, openableModuleIds),
        linear: normalizeLinearWorkspaceState(parsed.linear ?? null),
        layout: normalizeLayoutPreferences(parsed.layout ?? null, viewportWidth)
      };
    }

    return {
      modular: normalizeModularWorkspaceState(parsed, openableModuleIds),
      linear: defaultLinearWorkspaceState(viewportWidth),
      layout: defaultLayoutPreferences(viewportWidth)
    };
  } catch {
    return defaultRestoredState(viewportWidth);
  }
}

export function serializeLearningUnitWorkspaceState({
  modular,
  linear,
  layout
}: RestoredLearningUnitWorkspaceState): string {
  return JSON.stringify({
    version: LEARNING_UNIT_WORKSPACE_STORAGE_VERSION,
    modular,
    linear,
    layout
  });
}
