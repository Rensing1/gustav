export const TASK_COLUMN_PREFERENCE_VERSION = 1;
export const MIN_TASK_COLUMN_RATIO = 35;
export const MAX_TASK_COLUMN_RATIO = 65;

type ReadableStorage = {
  getItem?: (key: string) => string | null;
  get?: (key: string) => string | undefined;
};

type WritableStorage = ReadableStorage & {
  setItem?: (key: string, value: string) => void;
  set?: (key: string, value: string) => unknown;
  removeItem?: (key: string) => void;
  delete?: (key: string) => unknown;
};

export function clampTaskColumnRatio(value: number): number {
  return Math.min(MAX_TASK_COLUMN_RATIO, Math.max(MIN_TASK_COLUMN_RATIO, Math.round(value)));
}

export function taskColumnPreferenceStorageKey(learnerSub: string | null): string | null {
  if (!learnerSub) {
    return null;
  }
  return `gustav.learning.task-column-ratio:${encodeURIComponent(learnerSub)}`;
}

function storageGet(storage: ReadableStorage, key: string): string | null {
  if (typeof storage.getItem === "function") {
    return storage.getItem(key);
  }
  return storage.get?.(key) ?? null;
}

export function readTaskColumnRatio(storage: ReadableStorage | null, learnerSub: string | null): number | null {
  const key = taskColumnPreferenceStorageKey(learnerSub);
  if (!storage || !key) {
    return null;
  }

  try {
    const raw = storageGet(storage, key);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as { version?: unknown; taskColumnRatio?: unknown };
    const ratio = parsed.taskColumnRatio;
    if (
      parsed.version !== TASK_COLUMN_PREFERENCE_VERSION ||
      typeof ratio !== "number" ||
      !Number.isFinite(ratio) ||
      ratio < MIN_TASK_COLUMN_RATIO ||
      ratio > MAX_TASK_COLUMN_RATIO
    ) {
      return null;
    }
    return Math.round(ratio);
  } catch {
    return null;
  }
}

export function writeTaskColumnRatio(
  storage: WritableStorage | null,
  learnerSub: string | null,
  value: number
): void {
  const key = taskColumnPreferenceStorageKey(learnerSub);
  if (!storage || !key || !Number.isFinite(value)) {
    return;
  }

  const serialized = JSON.stringify({
    version: TASK_COLUMN_PREFERENCE_VERSION,
    taskColumnRatio: clampTaskColumnRatio(value)
  });
  try {
    if (typeof storage.setItem === "function") {
      storage.setItem(key, serialized);
    } else {
      storage.set?.(key, serialized);
    }
  } catch {
    // A blocked browser store must not prevent a learner from working.
  }
}

export function removeTaskColumnRatio(storage: WritableStorage | null, learnerSub: string | null): void {
  const key = taskColumnPreferenceStorageKey(learnerSub);
  if (!storage || !key) {
    return;
  }

  try {
    if (typeof storage.removeItem === "function") {
      storage.removeItem(key);
    } else {
      storage.delete?.(key);
    }
  } catch {
    // Resetting other presentation settings should still succeed without storage access.
  }
}
