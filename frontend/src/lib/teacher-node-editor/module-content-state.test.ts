import { describe, expect, it } from "vitest";

import {
  contentSelectionParam,
  draftStorageKey,
  formatPrerequisiteSummary,
  hasMeaningfulDraftChanges,
  hasMeaningfulTaskDraftChanges,
  parseContentSelection,
  taskDraftSnapshot,
} from "./module-content-state";

const content = {
  materials: [{ id: "material-1" }, { id: "material-2" }],
  tasks: [{ id: "task-1" }]
};

describe("module content state", () => {
  it("starts in the overview without a content parameter", () => {
    expect(parseContentSelection(null, content)).toEqual({ kind: "overview" });
  });

  it("resolves valid material and task selections", () => {
    expect(parseContentSelection("material:material-2", content)).toEqual({
      kind: "material",
      id: "material-2"
    });
    expect(parseContentSelection("task:task-1", content)).toEqual({ kind: "task", id: "task-1" });
  });

  it("falls back safely for malformed or inaccessible selections", () => {
    expect(parseContentSelection("material:foreign", content)).toEqual({ kind: "overview" });
    expect(parseContentSelection("task:", content)).toEqual({ kind: "overview" });
    expect(parseContentSelection("unknown:task-1", content)).toEqual({ kind: "overview" });
  });

  it("serializes only persisted content selections", () => {
    expect(contentSelectionParam({ kind: "material", id: "material-1" })).toBe("material:material-1");
    expect(contentSelectionParam({ kind: "task", id: "task-1" })).toBe("task:task-1");
    expect(contentSelectionParam({ kind: "overview" })).toBeNull();
    expect(contentSelectionParam({ kind: "new-material" })).toBeNull();
  });

  it("scopes drafts by teacher, unit, module and target", () => {
    const first = draftStorageKey({
      teacherSub: "teacher-1",
      unitId: "unit-1",
      nodeId: "module-1",
      target: "task:task-1"
    });
    const secondTeacher = draftStorageKey({
      teacherSub: "teacher-2",
      unitId: "unit-1",
      nodeId: "module-1",
      target: "task:task-1"
    });

    expect(first).toContain("teacher-1");
    expect(first).toContain("unit-1");
    expect(first).toContain("module-1");
    expect(first).toContain("task%3Atask-1");
    expect(secondTeacher).not.toBe(first);
  });

  it("formats the module prerequisite rule in plain language", () => {
    expect(formatPrerequisiteSummary(0, 0)).toBe("Keine Voraussetzungen");
    expect(formatPrerequisiteSummary(1, 2)).toBe("Freigabe nach 1 von 2 Voraussetzungen");
    expect(formatPrerequisiteSummary(2, 3)).toBe("Freigabe nach 2 von 3 Voraussetzungen");
  });

  it("distinguishes unchanged, changed and fully reverted form snapshots", () => {
    const baseline = {
      kind: "markdown",
      title: "Merkblatt",
      body_md: "Gespeicherter Inhalt",
      alt_text: ""
    };

    expect(hasMeaningfulDraftChanges({ ...baseline }, baseline)).toBe(false);
    expect(hasMeaningfulDraftChanges({ ...baseline, title: "Merkblatt überarbeitet" }, baseline)).toBe(true);
    expect(hasMeaningfulDraftChanges({ ...baseline, title: "Merkblatt" }, baseline)).toBe(false);
    expect(hasMeaningfulDraftChanges({ kind: "markdown", title: "Merkblatt", body_md: "Gespeicherter Inhalt" }, baseline)).toBe(false);
  });

  it("builds the persisted form snapshot for a normal learning task", () => {
    expect(taskDraftSnapshot({
      id: "task-1",
      kind: "native",
      instruction_md: "Begründe deine Antwort.",
      criteria: ["Klarheit", "Fachlichkeit"],
      teacher_context_md: "Interner Kontext",
      model_solution_md: "Eine Musterlösung",
      due_at: "2026-09-04T10:30:00+02:00",
      max_attempts: 3,
      position: 1
    }, "learning")).toEqual({
      module_kind: "learning",
      task_kind: "native",
      instruction_md: "Begründe deine Antwort.",
      "criteria[]": ["Klarheit", "Fachlichkeit"],
      teacher_context_md: "Interner Kontext",
      model_solution_md: "Eine Musterlösung",
      due_at: "2026-09-04T10:30",
      max_attempts: "3"
    });
  });

  it("includes only the fields rendered for H5P and practice tasks", () => {
    expect(taskDraftSnapshot({
      id: "task-h5p",
      kind: "h5p",
      instruction_md: "H5P-Aufgabe",
      criteria: [],
      teacher_context_md: "Nicht gerendert",
      model_solution_md: "Nicht gerendert",
      due_at: "2026-09-04T10:30:00+02:00",
      max_attempts: 2,
      position: 1,
      h5p: { content_id: "42" }
    }, "learning")).toEqual({
      module_kind: "learning",
      task_kind: "h5p",
      instruction_md: "H5P-Aufgabe",
      h5p_content_id: "42"
    });

    expect(taskDraftSnapshot({
      id: "task-practice",
      kind: "native",
      instruction_md: "Übe die Begründung.",
      criteria: ["Klarheit"],
      teacher_context_md: "Kontext",
      model_solution_md: "Lösung",
      due_at: "2026-09-04T10:30:00+02:00",
      max_attempts: 2,
      position: 1
    }, "practice")).toEqual({
      module_kind: "practice",
      task_kind: "native",
      instruction_md: "Übe die Begründung.",
      "criteria[]": ["Klarheit"],
      teacher_context_md: "Kontext",
      model_solution_md: "Lösung"
    });
  });

  it("captures every dialog field in the task baseline", () => {
    const snapshot = taskDraftSnapshot({
      id: "task-dialog",
      kind: "dialog",
      instruction_md: "Diskutiere die These.",
      criteria: ["Begründung"],
      teacher_context_md: null,
      model_solution_md: null,
      due_at: null,
      max_attempts: null,
      position: 1,
      dialog: {
        partner_name: "Dr. Dialog",
        partner_description_md: "Kurzbeschreibung",
        role_md: "Stelle Rückfragen.",
        learning_goal_md: "Argumente prüfen",
        opening_message_md: "Wie lautet deine Position?",
        response_mode: "hybrid",
        max_rounds: 7,
        closing_prompt_md: "Fasse zusammen."
      }
    }, "learning");

    expect(snapshot).toMatchObject({
      dialog_partner_name: "Dr. Dialog",
      dialog_partner_description_md: "Kurzbeschreibung",
      dialog_role_md: "Stelle Rückfragen.",
      dialog_learning_goal_md: "Argumente prüfen",
      dialog_opening_message_md: "Wie lautet deine Position?",
      dialog_response_mode: "hybrid",
      dialog_max_rounds: "7",
      dialog_closing_prompt_md: "Fasse zusammen."
    });
  });

  it.each(["visual", "scratch", "calliope", "filius"] as const)(
    "uses the shared editable fields for a %s task",
    (kind) => {
      const snapshot = taskDraftSnapshot({
        id: `task-${kind}`,
        kind,
        instruction_md: "Untersuche das Ergebnis.",
        criteria: [],
        teacher_context_md: null,
        model_solution_md: null,
        due_at: null,
        max_attempts: null,
        position: 1
      }, "learning");

      expect(snapshot.task_kind).toBe(kind);
      expect(snapshot).toHaveProperty("instruction_md", "Untersuche das Ergebnis.");
      expect(snapshot).toHaveProperty("criteria[]", []);
      expect(snapshot).not.toHaveProperty("h5p_content_id");
      expect(snapshot).not.toHaveProperty("dialog_partner_name");
    }
  );

  it("compares task snapshots with the same normalization as task persistence", () => {
    const baseline = {
      module_kind: "learning",
      task_kind: "native",
      instruction_md: "Begründe deine Antwort.",
      "criteria[]": ["Klarheit", "Fachlichkeit"],
      teacher_context_md: "",
      model_solution_md: "",
      due_at: "",
      max_attempts: ""
    };

    expect(hasMeaningfulTaskDraftChanges({
      ...baseline,
      instruction_md: "  Begründe deine Antwort.\n",
      "criteria[]": [" Klarheit ", "", "Fachlichkeit"]
    }, baseline)).toBe(false);
    expect(hasMeaningfulTaskDraftChanges({
      ...baseline,
      instruction_md: "Begründe deine Antwort ausführlich."
    }, baseline)).toBe(true);
    expect(hasMeaningfulTaskDraftChanges({
      ...baseline,
      "criteria[]": ["Fachlichkeit", "Klarheit"]
    }, baseline)).toBe(true);
    expect(hasMeaningfulTaskDraftChanges({
      module_kind: "learning",
      task_kind: "native",
      instruction_md: "Begründe deine Antwort.",
      "criteria[]": ["Klarheit", "Fachlichkeit"]
    }, baseline)).toBe(false);
  });
});
