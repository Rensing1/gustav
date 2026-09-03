export type LearnerSurface = "graph" | "reading" | "task";
export type LearnerResultPanel = "result" | null;

export type LearnerNavigationTarget = {
  surface: LearnerSurface;
  moduleId: string | null;
  taskId: string | null;
  panel: LearnerResultPanel;
};

export type LearnerNavigationState = LearnerNavigationTarget & {
  needsNormalization: boolean;
};

export type LearnerHistoryEntry = Record<string, unknown> & {
  gustavLearnerSurface: LearnerSurface;
  gustavLearnerHref: string;
  gustavLearnerParentHref?: string;
};

type LearnerNavigationAccess = {
  unitType: "linear" | "modular";
  openableModuleIds: Set<string>;
  taskModuleIds: Map<string, string | null>;
};

/**
 * Resolve the visible learner surface from the canonical URL.
 *
 * The caller supplies already-authorized IDs. Stale or forged links can
 * therefore only resolve to content the learner may currently open.
 */
export function resolveLearnerNavigation(url: URL, access: LearnerNavigationAccess): LearnerNavigationState {
  const legacyView = url.searchParams.get("view");
  const legacyHistory = url.searchParams.get("history");
  const requestedModule = url.searchParams.get("module");
  const requestedTask = url.searchParams.get("task") ?? legacyHistory;
  const requestedPanel = url.searchParams.get("panel") === "result" || legacyHistory ? "result" : null;
  const hasLegacyState = legacyView !== null || legacyHistory !== null;

  if (access.unitType === "linear") {
    const taskId = requestedTask && access.taskModuleIds.has(requestedTask) ? requestedTask : null;
    return {
      surface: taskId ? "task" : "reading",
      moduleId: null,
      taskId,
      panel: taskId ? requestedPanel : null,
      needsNormalization: hasLegacyState || Boolean(requestedModule) || Boolean(requestedTask && !taskId)
    };
  }

  const moduleId = requestedModule && access.openableModuleIds.has(requestedModule) ? requestedModule : null;
  if (!moduleId) {
    return {
      surface: "graph",
      moduleId: null,
      taskId: null,
      panel: null,
      needsNormalization: hasLegacyState || Boolean(requestedModule) || Boolean(requestedTask) || requestedPanel !== null
    };
  }

  const taskId = requestedTask && access.taskModuleIds.get(requestedTask) === moduleId ? requestedTask : null;
  return {
    surface: taskId ? "task" : "reading",
    moduleId,
    taskId,
    panel: taskId ? requestedPanel : null,
    needsNormalization: hasLegacyState || Boolean(requestedTask && !taskId) || (requestedPanel !== null && !taskId)
  };
}

/** Build a canonical in-app URL while discarding obsolete transient parameters. */
export function learnerNavigationHref(url: URL, target: LearnerNavigationTarget): string {
  const next = new URL(url);
  for (const key of ["view", "history", "submitted", "message", "submission_mode"]) {
    next.searchParams.delete(key);
  }
  next.searchParams.delete("module");
  next.searchParams.delete("task");
  next.searchParams.delete("panel");

  if (target.surface !== "graph" && target.moduleId) next.searchParams.set("module", target.moduleId);
  if (target.surface === "task" && target.taskId) next.searchParams.set("task", target.taskId);
  if (target.surface === "task" && target.taskId && target.panel === "result") {
    next.searchParams.set("panel", "result");
  }

  const query = next.searchParams.toString();
  return query ? `${next.pathname}?${query}` : next.pathname;
}

/** Preserve framework state while recording the exact in-app parent of a new entry. */
export function learnerHistoryEntryState(
  currentState: unknown,
  surface: LearnerSurface,
  href: string,
  parentHref?: string
): LearnerHistoryEntry {
  const base = currentState && typeof currentState === "object"
    ? currentState as Record<string, unknown>
    : {};
  const next: LearnerHistoryEntry = {
    ...base,
    gustavLearnerSurface: surface,
    gustavLearnerHref: href
  };
  if (parentHref) {
    next.gustavLearnerParentHref = parentHref;
  } else {
    delete next.gustavLearnerParentHref;
  }
  return next;
}

/** Browser Back is safe only when GUSTAV recorded this exact current/parent pair. */
export function canUseLearnerHistoryParent(
  state: unknown,
  currentHref: string,
  targetHref: string
): boolean {
  if (!state || typeof state !== "object") {
    return false;
  }
  const candidate = state as Partial<LearnerHistoryEntry>;
  return candidate.gustavLearnerHref === currentHref &&
    candidate.gustavLearnerParentHref === targetHref;
}
