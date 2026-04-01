import type {
  LearningMaterial,
  LearningModuleContent,
  LearningSection,
  LearningTask
} from "$lib/types/learning";

export type PaneId = "left" | "right";

export type PaneStacks = Record<PaneId, string[]>;

export type LearningContentKind = "material" | "task";

export type LearningContentItem = {
  key: string;
  kind: LearningContentKind;
  title: string;
  position: number;
  contextLabel: string | null;
  material?: LearningMaterial;
  task?: LearningTask;
};

export type ContentGroup = {
  id: string;
  title: string | null;
  items: LearningContentItem[];
};

export function emptyPaneStacks(): PaneStacks {
  return {
    left: [],
    right: []
  };
}

export function normalizePaneStacks(raw: unknown): PaneStacks | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const candidate = raw as Partial<PaneStacks>;
  return {
    left: Array.isArray(candidate.left) ? candidate.left.map(String).filter(Boolean) : [],
    right: Array.isArray(candidate.right) ? candidate.right.map(String).filter(Boolean) : []
  };
}

export function defaultPaneStacks(itemKeys: string[], splitView: boolean): PaneStacks {
  return {
    left: [...itemKeys],
    right: splitView ? [...itemKeys] : []
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
    material
  }));
  const tasks = (module.tasks ?? []).map((task, index) => ({
    key: `task:${task.id}`,
    kind: "task" as const,
    title: `Aufgabe ${task.position ?? index + 1}`,
    position: Number(task.position ?? index + 1),
    contextLabel: null,
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
    material
  }));
  const tasks = section.tasks.map((task, index) => ({
    key: `task:${task.id}`,
    kind: "task" as const,
    title: `Aufgabe ${task.position ?? index + 1}`,
    position: Number(task.position ?? index + 1),
    contextLabel: section.section.title,
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

export function filterPaneStacks(stacks: PaneStacks, allowedKeys: Set<string>): PaneStacks {
  return {
    left: stacks.left.filter((key) => allowedKeys.has(key)),
    right: stacks.right.filter((key) => allowedKeys.has(key))
  };
}
