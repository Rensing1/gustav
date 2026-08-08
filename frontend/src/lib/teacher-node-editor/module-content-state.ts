export type ModuleContentSelection =
  | { kind: "overview" }
  | { kind: "material"; id: string }
  | { kind: "task"; id: string }
  | { kind: "new-material" }
  | { kind: "new-task" };

type ContentIds = {
  materials: Array<{ id: string }>;
  tasks: Array<{ id: string }>;
};

/**
 * Resolve an addressable editor selection without trusting the URL alone.
 * Only identifiers present in the authorized editor read model may be opened.
 */
export function parseContentSelection(
  raw: string | null,
  content: ContentIds
): ModuleContentSelection {
  if (!raw) {
    return { kind: "overview" };
  }

  const separator = raw.indexOf(":");
  if (separator <= 0 || separator === raw.length - 1) {
    return { kind: "overview" };
  }

  const kind = raw.slice(0, separator);
  const id = raw.slice(separator + 1);
  if (kind === "material" && content.materials.some((item) => item.id === id)) {
    return { kind: "material", id };
  }
  if (kind === "task" && content.tasks.some((item) => item.id === id)) {
    return { kind: "task", id };
  }
  return { kind: "overview" };
}

export function contentSelectionParam(selection: ModuleContentSelection): string | null {
  if (selection.kind === "material" || selection.kind === "task") {
    return `${selection.kind}:${selection.id}`;
  }
  return null;
}

export function draftStorageKey(options: {
  teacherSub: string;
  unitId: string;
  nodeId: string;
  target: string;
}): string {
  const parts = [options.teacherSub, options.unitId, options.nodeId, options.target].map(encodeURIComponent);
  return `gustav:teacher-module-draft:v1:${parts.join(":")}`;
}

export function formatPrerequisiteSummary(required: number, incoming: number): string {
  if (incoming <= 0) {
    return "Keine Voraussetzungen";
  }
  return `Freigabe nach ${required} von ${incoming} Voraussetzungen`;
}
