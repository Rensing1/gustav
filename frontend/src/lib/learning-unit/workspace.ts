import type {
  LearningMaterial,
  LearningModuleContent,
  LearningUnitGraph,
  LearningUnitGraphModule,
  LearningSection,
  LearningTask
} from "$lib/types/learning";

export type PaneId = "left" | "right";

export type PaneStackEntry = {
  key: string;
  expanded: boolean;
};

export type PaneStacks = Record<PaneId, PaneStackEntry[]>;

export type SubmissionFocusState = {
  itemKey: string | null;
  mode: "text" | "upload" | null;
};

export type SubmissionFocusByPane = Record<PaneId, SubmissionFocusState>;

export type ReviewFocusByPane = Record<PaneId, string | null>;

export type LearningContentKind = "material" | "task";

export type LearningContentItem = {
  key: string;
  kind: LearningContentKind;
  title: string;
  position: number;
  contextLabel: string | null;
  moduleId?: string | null;
  material?: LearningMaterial;
  task?: LearningTask;
};

export type ContentGroup = {
  id: string;
  title: string | null;
  items: LearningContentItem[];
};

export type LearningUnitViewState = "overview" | "content";

export type ModularWorkspaceSnapshot = {
  view: LearningUnitViewState;
  openTabs: string[];
  activeTab: string | null;
};

export type ModularWorkspaceReconciliationInput = {
  moduleOrder: string[];
  openableModuleIds: Set<string>;
  requestedView: LearningUnitViewState;
  requestedModuleId: string | null;
};

export function emptyPaneStacks(): PaneStacks {
  return {
    left: [],
    right: []
  };
}

export function emptySubmissionFocus(): SubmissionFocusByPane {
  return {
    left: { itemKey: null, mode: null },
    right: { itemKey: null, mode: null }
  };
}

export function emptyReviewFocus(): ReviewFocusByPane {
  return {
    left: null,
    right: null
  };
}

export function setPaneSubmissionFocus(
  submissionFocus: SubmissionFocusByPane,
  reviewFocus: ReviewFocusByPane,
  paneId: PaneId,
  itemKey: string | null,
  mode: "text" | "upload" | null
): { submissionFocus: SubmissionFocusByPane; reviewFocus: ReviewFocusByPane } {
  return {
    submissionFocus: {
      ...submissionFocus,
      [paneId]: { itemKey, mode }
    },
    reviewFocus: {
      ...reviewFocus,
      [paneId]: itemKey ? null : reviewFocus[paneId]
    }
  };
}

export function togglePaneSubmissionFocus(
  submissionFocus: SubmissionFocusByPane,
  reviewFocus: ReviewFocusByPane,
  paneId: PaneId,
  itemKey: string,
  mode: "text" | "upload"
): { submissionFocus: SubmissionFocusByPane; reviewFocus: ReviewFocusByPane } {
  const current = submissionFocus[paneId];
  const sameTarget = current.itemKey === itemKey && current.mode === mode;

  if (sameTarget) {
    return setPaneSubmissionFocus(submissionFocus, reviewFocus, paneId, null, null);
  }

  return setPaneSubmissionFocus(submissionFocus, reviewFocus, paneId, itemKey, mode);
}

export function setPaneReviewFocus(
  submissionFocus: SubmissionFocusByPane,
  reviewFocus: ReviewFocusByPane,
  paneId: PaneId,
  itemKey: string | null
): { submissionFocus: SubmissionFocusByPane; reviewFocus: ReviewFocusByPane } {
  return {
    submissionFocus: {
      ...submissionFocus,
      [paneId]: itemKey ? { itemKey: null, mode: null } : submissionFocus[paneId]
    },
    reviewFocus: {
      ...reviewFocus,
      [paneId]: itemKey
    }
  };
}

export function togglePaneReviewFocus(
  submissionFocus: SubmissionFocusByPane,
  reviewFocus: ReviewFocusByPane,
  paneId: PaneId,
  itemKey: string
): { submissionFocus: SubmissionFocusByPane; reviewFocus: ReviewFocusByPane } {
  const sameTarget = reviewFocus[paneId] === itemKey;

  if (sameTarget) {
    return setPaneReviewFocus(submissionFocus, reviewFocus, paneId, null);
  }

  return setPaneReviewFocus(submissionFocus, reviewFocus, paneId, itemKey);
}

export function normalizePaneStacks(raw: unknown): PaneStacks | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const candidate = raw as Partial<PaneStacks>;
  function normalizeEntries(value: unknown): PaneStackEntry[] {
    if (!Array.isArray(value)) {
      return [];
    }

    return value
      .map((entry) => {
        if (typeof entry === "string") {
          return { key: entry, expanded: true };
        }
        if (entry && typeof entry === "object" && "key" in entry) {
          return {
            key: String((entry as { key: unknown }).key),
            expanded: (entry as { expanded?: unknown }).expanded !== false
          };
        }
        return null;
      })
      .filter((entry): entry is PaneStackEntry => Boolean(entry?.key));
  }

  return {
    left: normalizeEntries(candidate.left),
    right: normalizeEntries(candidate.right)
  };
}

export function defaultPaneStacks(itemKeys: string[], splitView: boolean): PaneStacks {
  const entries = itemKeys.map((key) => ({ key, expanded: true }));
  return {
    left: [...entries],
    right: splitView ? [...entries] : []
  };
}

export function sortContentItems(left: LearningContentItem, right: LearningContentItem): number {
  if (left.position !== right.position) {
    return left.position - right.position;
  }
  if (left.kind !== right.kind) {
    return left.kind.localeCompare(right.kind, "de");
  }
  return left.title.localeCompare(right.title, "de");
}

export function moduleContentItems(module: LearningModuleContent | null): LearningContentItem[] {
  if (!module) {
    return [];
  }

  const materials = (module.materials ?? []).map((material, index) => ({
    key: `material:${material.id}`,
    kind: "material" as const,
    title: material.title,
    position: Number(material.position ?? index + 1),
    contextLabel: null,
    moduleId: module.module.id,
    material
  }));
  const tasks = (module.tasks ?? []).map((task, index) => ({
    key: `task:${task.id}`,
    kind: "task" as const,
    title: `Aufgabe ${task.position ?? index + 1}`,
    position: Number(task.position ?? index + 1),
    contextLabel: null,
    moduleId: module.module.id,
    task
  }));

  return [...materials, ...tasks].sort(sortContentItems);
}

export function sectionContentItems(section: LearningSection): LearningContentItem[] {
  const materials = section.materials.map((material, index) => ({
    key: `material:${material.id}`,
    kind: "material" as const,
    title: material.title,
    position: Number(material.position ?? index + 1),
    contextLabel: section.section.title,
    moduleId: null,
    material
  }));
  const tasks = section.tasks.map((task, index) => ({
    key: `task:${task.id}`,
    kind: "task" as const,
    title: `Aufgabe ${task.position ?? index + 1}`,
    position: Number(task.position ?? index + 1),
    contextLabel: section.section.title,
    moduleId: null,
    task
  }));

  return [...materials, ...tasks].sort(sortContentItems);
}

export function contentGroupsForModule(
  activeModuleId: string | null,
  module: LearningModuleContent | null
): ContentGroup[] {
  const items = moduleContentItems(module);
  if (!items.length) {
    return [];
  }

  return [
    {
      id: activeModuleId ?? "module",
      title: null,
      items
    }
  ];
}

function graphModuleOrder(
  graph: LearningUnitGraph,
  left: LearningUnitGraphModule,
  right: LearningUnitGraphModule
): number {
  const phasePositions = new Map(graph.phases.map((phase) => [phase.id, phase.position]));
  const leftPhase = phasePositions.get(left.phase_id) ?? Number.MAX_SAFE_INTEGER;
  const rightPhase = phasePositions.get(right.phase_id) ?? Number.MAX_SAFE_INTEGER;

  if (leftPhase !== rightPhase) {
    return leftPhase - rightPhase;
  }
  if (left.position_in_phase !== right.position_in_phase) {
    return left.position_in_phase - right.position_in_phase;
  }
  return left.title.localeCompare(right.title, "de");
}

export function orderedOpenModules(
  graph: LearningUnitGraph | null,
  openModuleIds: string[]
): LearningUnitGraphModule[] {
  if (!graph) {
    return [];
  }

  const openIdSet = new Set(openModuleIds);
  return [...graph.modules]
    .filter((module) => openIdSet.has(module.id))
    .sort((left, right) => graphModuleOrder(graph, left, right));
}

export function contentGroupsForModules(
  graph: LearningUnitGraph | null,
  openModuleIds: string[],
  moduleCache: Record<string, LearningModuleContent>
): ContentGroup[] {
  return orderedOpenModules(graph, openModuleIds)
    .map((moduleSummary) => {
      const module = moduleCache[moduleSummary.id] ?? null;
      const items = moduleContentItems(module).map((item) => ({
        ...item,
        contextLabel: moduleSummary.title
      }));

      return {
        id: moduleSummary.id,
        title: moduleSummary.title,
        items
      };
    })
    .filter((group) => group.items.length > 0);
}

export function contentGroupsForSections(sections: LearningSection[]): ContentGroup[] {
  return sections
    .map((section) => ({
      id: section.section.id,
      title: `Abschnitt ${section.section.position}`,
      items: sectionContentItems(section)
    }))
    .filter((group) => group.items.length > 0);
}

export function flattenContentGroups(groups: ContentGroup[]): LearningContentItem[] {
  return groups.flatMap((group) => group.items);
}

export function reconcileModularWorkspaceState(
  workspace: ModularWorkspaceSnapshot,
  input: ModularWorkspaceReconciliationInput
): ModularWorkspaceSnapshot {
  const allowed = input.openableModuleIds;
  const orderedOpenTabs = input.moduleOrder.filter((moduleId) =>
    workspace.openTabs.includes(moduleId) && allowed.has(moduleId)
  );

  const requestedModuleId =
    input.requestedModuleId && allowed.has(input.requestedModuleId) ? input.requestedModuleId : null;
  const activeTab =
    requestedModuleId
    ?? (workspace.activeTab && orderedOpenTabs.includes(workspace.activeTab) ? workspace.activeTab : orderedOpenTabs[0] ?? null);

  if (input.requestedView === "overview") {
    return {
      view: "overview",
      openTabs: orderedOpenTabs,
      activeTab
    };
  }

  if (!activeTab) {
    return {
      view: "overview",
      openTabs: orderedOpenTabs,
      activeTab: null
    };
  }

  const openTabs = orderedOpenTabs.includes(activeTab) ? orderedOpenTabs : [...orderedOpenTabs, activeTab];
  return {
    view: "content",
    openTabs,
    activeTab
  };
}

export function filterPaneStacks(stacks: PaneStacks, allowedKeys: Set<string>): PaneStacks {
  return {
    left: stacks.left.filter((entry) => allowedKeys.has(entry.key)),
    right: stacks.right.filter((entry) => allowedKeys.has(entry.key))
  };
}

export function reconcilePaneStacks(
  stacks: PaneStacks | null,
  itemKeys: string[],
  splitView: boolean
): PaneStacks {
  if (!stacks) {
    return defaultPaneStacks(itemKeys, splitView);
  }

  const allowed = new Set(itemKeys);
  const filtered = filterPaneStacks(stacks, allowed);

  function canonicalEntries(existing: PaneStackEntry[]): PaneStackEntry[] {
    const stateByKey = new Map(existing.map((entry) => [entry.key, entry.expanded]));
    return itemKeys.map((key) => ({
      key,
      expanded: stateByKey.get(key) ?? true
    }));
  }

  return {
    left: canonicalEntries(filtered.left),
    right: splitView ? canonicalEntries(filtered.right) : []
  };
}

export function reopenMaterialEntries(
  entries: PaneStackEntry[],
  items: LearningContentItem[],
  moduleIds: string[]
): PaneStackEntry[] {
  const targetModules = new Set(moduleIds);
  const materialKeys = new Set(
    items
      .filter((item) => item.kind === "material" && item.moduleId && targetModules.has(item.moduleId))
      .map((item) => item.key)
  );

  if (!materialKeys.size) {
    return entries;
  }

  return entries.map((entry) =>
    materialKeys.has(entry.key) && !entry.expanded ? { ...entry, expanded: true } : entry
  );
}
