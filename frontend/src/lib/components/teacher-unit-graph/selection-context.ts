export type TeacherGraphSelectionKind = "section" | "phase" | "module";
export type TeacherGraphSelectionHandler = (kind: TeacherGraphSelectionKind, id: string) => void;

export const TEACHER_GRAPH_SELECTION_CONTEXT = Symbol("teacher-graph-selection");
