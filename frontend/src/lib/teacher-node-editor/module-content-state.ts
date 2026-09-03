import type {
  TeacherUnitNodeEditorMaterial,
  TeacherUnitNodeEditorTask
} from "$lib/types/home";

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

export type ModuleDraftSnapshot = Record<string, string | string[]>;
export type ModuleKind = "learning" | "practice";

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

/** Builds the form-shaped baseline for one persisted material. */
export function materialDraftSnapshot(material: TeacherUnitNodeEditorMaterial): ModuleDraftSnapshot {
  const snapshot: ModuleDraftSnapshot = {
    kind: material.kind,
    title: material.title
  };
  if (material.kind === "markdown" || material.kind === "simulation") {
    snapshot.body_md = material.body_md ?? "";
  } else {
    snapshot.alt_text = material.alt_text ?? "";
  }
  return snapshot;
}

/** Builds exactly the values rendered by the existing-task form. */
export function taskDraftSnapshot(
  task: TeacherUnitNodeEditorTask,
  moduleKind: ModuleKind
): ModuleDraftSnapshot {
  if (task.kind === "h5p") {
    return {
      module_kind: moduleKind,
      task_kind: task.kind,
      instruction_md: task.instruction_md,
      h5p_content_id: task.h5p?.content_id ?? ""
    };
  }

  const snapshot: ModuleDraftSnapshot = {
    module_kind: moduleKind,
    task_kind: task.kind,
    instruction_md: task.instruction_md,
    "criteria[]": task.criteria,
    teacher_context_md: task.teacher_context_md ?? "",
    model_solution_md: task.model_solution_md ?? ""
  };

  if (moduleKind === "learning") {
    snapshot.due_at = task.due_at?.slice(0, 16) ?? "";
    snapshot.max_attempts = task.max_attempts ? String(task.max_attempts) : "";
  }

  if (task.kind === "dialog") {
    snapshot.dialog_partner_name = task.dialog?.partner_name ?? "";
    snapshot.dialog_partner_description_md = task.dialog?.partner_description_md ?? "";
    snapshot.dialog_role_md = task.dialog?.role_md ?? "";
    snapshot.dialog_learning_goal_md = task.dialog?.learning_goal_md ?? "";
    snapshot.dialog_opening_message_md = task.dialog?.opening_message_md ?? "";
    snapshot.dialog_response_mode = task.dialog?.response_mode ?? "free_text";
    snapshot.dialog_max_rounds = String(task.dialog?.max_rounds ?? 8);
    snapshot.dialog_closing_prompt_md = task.dialog?.closing_prompt_md ?? "";
  }

  return snapshot;
}

function normalizedDraftValue(value: string | string[] | undefined): string[] {
  if (value === undefined || value === "") {
    return [];
  }
  const entries = Array.isArray(value) ? value : [value];
  return entries.length === 1 && entries[0] === "" ? [] : entries;
}

/** Compares form values by meaning, treating an absent optional field like an empty field. */
export function hasMeaningfulDraftChanges(current: ModuleDraftSnapshot, baseline: ModuleDraftSnapshot): boolean {
  const fields = new Set([...Object.keys(current), ...Object.keys(baseline)]);
  return [...fields].some(
    (field) => JSON.stringify(normalizedDraftValue(current[field])) !== JSON.stringify(normalizedDraftValue(baseline[field]))
  );
}

function normalizedTaskDraftValue(field: string, value: string | string[] | undefined): string[] {
  const entries = (Array.isArray(value) ? value : value === undefined ? [] : [value])
    .map((entry) => entry.trim());
  if (field === "criteria[]") {
    return entries.filter(Boolean).slice(0, 10);
  }
  return entries.length === 1 && entries[0] === "" ? [] : entries;
}

/** Compares task values with the same trimming and criteria rules as the save action. */
export function hasMeaningfulTaskDraftChanges(
  current: ModuleDraftSnapshot,
  baseline: ModuleDraftSnapshot
): boolean {
  const fields = new Set([...Object.keys(current), ...Object.keys(baseline)]);
  return [...fields].some(
    (field) => JSON.stringify(normalizedTaskDraftValue(field, current[field]))
      !== JSON.stringify(normalizedTaskDraftValue(field, baseline[field]))
  );
}

export function formatPrerequisiteSummary(required: number, incoming: number): string {
  if (incoming <= 0) {
    return "Keine Voraussetzungen";
  }
  return `Freigabe nach ${required} von ${incoming} Voraussetzungen`;
}
