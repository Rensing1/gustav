import type { SessionBootstrapUser } from "$lib/types/session-bootstrap";

export type LearnerHomeCourse = {
  id: string;
  title: string;
  href: string;
};

export type LearnerHome = {
  user: SessionBootstrapUser;
  courses: LearnerHomeCourse[];
};

export type TeacherHomeEntry = {
  id: string;
  title: string;
  href: string;
  description: string;
};

export type TeacherHome = {
  user: SessionBootstrapUser;
  entries: TeacherHomeEntry[];
};

export type TeacherCourseListItem = {
  id: string;
  title: string;
  href: string;
  members_count: number;
  units_count: number;
  subject: string | null;
  grade_level: string | null;
  term: string | null;
};

export type TeacherCourseListView = {
  user: SessionBootstrapUser;
  courses: TeacherCourseListItem[];
};

export type TeacherCourseContextCourse = {
  id: string;
  title: string;
  href: string;
  members_href: string;
  diagnostics_href: string;
  members_count: number;
  units_count: number;
};

export type TeacherCourseContextUnit = {
  id: string;
  title: string;
  position: number;
  href: string;
};

export type TeacherCourseContextMember = {
  sub: string;
  name: string;
  href: string;
  joined_at: string;
};

export type TeacherCourseContextView = {
  user: SessionBootstrapUser;
  course: TeacherCourseContextCourse;
  units: TeacherCourseContextUnit[];
  members: TeacherCourseContextMember[];
};

export type TeacherUnitsCatalogOption = {
  id: string;
  label: string;
  active: boolean;
  href?: string | null;
};

export type TeacherUnitsCatalogItem = {
  id: string;
  title: string;
  topic?: string | null;
  meta: string;
  updated_at: string;
  href: string;
};

export type TeacherUnitsCatalogView = {
  user: SessionBootstrapUser;
  views: TeacherUnitsCatalogOption[];
  active_view: string;
  query: string;
  filters: {
    status: TeacherUnitsCatalogOption[];
    subjects: TeacherUnitsCatalogOption[];
    grade_levels: TeacherUnitsCatalogOption[];
    courses: TeacherUnitsCatalogOption[];
  };
  active_filters: {
    status: string;
    subject: string;
    grade_level: string;
    course_id: string;
  };
  sort: string;
  result_count: number;
  items: TeacherUnitsCatalogItem[];
  create_href: string;
};

export type TeacherUnitWorkspaceUnit = {
  id: string;
  title: string;
  summary?: string | null;
  unit_type: "linear" | "modular";
  edit_href: string;
};

export type TeacherUnitWorkspaceCounts = {
  sections_count: number;
  phases_count: number;
  modules_count: number;
  courses_count: number;
};

export type TeacherUnitWorkspaceSectionItem = {
  id: string;
  title: string;
  position: number;
  materials_count: number;
  tasks_count: number;
  editor_href: string;
};

export type TeacherUnitWorkspacePhaseItem = {
  id: string;
  title: string;
  position: number;
};

export type TeacherUnitWorkspaceModuleItem = {
  id: string;
  title: string;
  phase_id: string;
  position_in_phase: number;
  required_prereq_count: number;
  materials_count: number;
  tasks_count: number;
  editor_href: string;
  section_id?: string | null;
};

export type TeacherUnitWorkspaceEdge = {
  from: string;
  to: string;
};

export type TeacherUnitNodeEditorMaterial = {
  id: string;
  title: string;
  kind: "markdown" | "file";
  position: number;
  body_md?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  filename_original?: string | null;
  alt_text?: string | null;
};

export type TeacherUnitNodeEditorTask = {
  id: string;
  instruction_md: string;
  criteria: string[];
  teacher_context_md?: string | null;
  due_at?: string | null;
  max_attempts?: number | null;
  position: number;
  kind: "native" | "h5p" | "visual" | "scratch" | "calliope";
  h5p?: {
    content_id?: string | null;
    display_options?: Record<string, unknown> | null;
  } | null;
  visual?: Record<string, never> | null;
  scratch?: Record<string, never> | null;
  calliope?: Record<string, never> | null;
};

export type TeacherUnitWorkspaceSelectionSection = {
  id: string;
  title: string;
  position: number;
  editor_href: string;
};

export type TeacherUnitWorkspaceGraphPhase = {
  id: string;
  title: string;
  position: number;
  modules: TeacherUnitWorkspaceModuleItem[];
};

export type TeacherUnitWorkspaceEdgeSelection = {
  from_id: string;
  to_id: string;
  from_title: string;
  to_title: string;
  exists: boolean;
};

export type TeacherUnitWorkspaceSelectionPhase = {
  id: string;
  title: string;
  position: number;
};

export type TeacherUnitWorkspaceSelectionModule = {
  id: string;
  title: string;
  phase_id: string;
  position_in_phase: number;
  required_prereq_count: number;
  materials_count: number;
  tasks_count: number;
  editor_href: string;
};

export type TeacherUnitWorkspaceSelection =
  | { kind: "none" }
  | { kind: "section"; section: TeacherUnitWorkspaceSelectionSection }
  | { kind: "phase"; phase: TeacherUnitWorkspaceSelectionPhase }
  | { kind: "module"; module: TeacherUnitWorkspaceSelectionModule }
  | { kind: "edge"; edge: TeacherUnitWorkspaceEdgeSelection };

export type TeacherUnitWorkspaceGraph = {
  kind: "linear" | "modular";
  create_section_href?: string | null;
  create_phase_href?: string | null;
  create_module_href?: string | null;
  nodes?: TeacherUnitWorkspaceSectionItem[];
  phases?: TeacherUnitWorkspaceGraphPhase[];
  edges?: TeacherUnitWorkspaceEdge[];
};

export type TeacherUnitWorkspaceView = {
  user: SessionBootstrapUser;
  unit: TeacherUnitWorkspaceUnit;
  counts: TeacherUnitWorkspaceCounts;
  graph: TeacherUnitWorkspaceGraph;
  selection: TeacherUnitWorkspaceSelection;
};

export type TeacherUnitNodeEditorNode = {
  id: string;
  kind: "section" | "module";
  title: string;
  editor_title: string;
  backing_section_id?: string | null;
};

export type TeacherUnitNodeEditorSettings =
  | { kind: "section" }
  | { kind: "module"; required_prereq_count: number };

export type TeacherUnitNodeEditorView = {
  user: SessionBootstrapUser;
  unit: TeacherUnitWorkspaceUnit;
  node: TeacherUnitNodeEditorNode;
  materials: TeacherUnitNodeEditorMaterial[];
  tasks: TeacherUnitNodeEditorTask[];
  settings: TeacherUnitNodeEditorSettings;
};

export type DiagnosticsCourseMatrixCourse = {
  id: string;
  title: string;
  href: string;
};

export type DiagnosticsCourseMatrixUnit = {
  id: string;
  title: string;
  position: number;
  href: string;
};

export type DiagnosticsCourseMatrixStudent = {
  sub: string;
  name: string;
  href: string;
};

export type DiagnosticsCourseMatrixCell = {
  unit_id: string;
  submitted_tasks: number;
  total_tasks: number;
  href: string;
};

export type DiagnosticsCourseMatrixRow = {
  student: DiagnosticsCourseMatrixStudent;
  cells: DiagnosticsCourseMatrixCell[];
};

export type DiagnosticsCourseMatrixView = {
  user: SessionBootstrapUser;
  course: DiagnosticsCourseMatrixCourse;
  units: DiagnosticsCourseMatrixUnit[];
  rows: DiagnosticsCourseMatrixRow[];
};

export type DiagnosticsLearnerProfileLearner = {
  sub: string;
  name: string;
  href: string;
};

export type DiagnosticsLearnerProfileSummary = {
  courses_count: number;
  submitted_tasks: number;
  total_tasks: number;
};

export type DiagnosticsLearnerProfileUnit = {
  id: string;
  title: string;
  position: number;
  href: string;
  submitted_tasks: number;
  total_tasks: number;
};

export type DiagnosticsLearnerProfileCourse = {
  id: string;
  title: string;
  href: string;
  submitted_tasks: number;
  total_tasks: number;
  units: DiagnosticsLearnerProfileUnit[];
};

export type DiagnosticsLearnerProfileView = {
  user: SessionBootstrapUser;
  learner: DiagnosticsLearnerProfileLearner;
  summary: DiagnosticsLearnerProfileSummary;
  courses: DiagnosticsLearnerProfileCourse[];
};

export type LiveCourseRef = {
  id: string;
  title: string;
  href: string;
};

export type LiveUnitRef = {
  id: string;
  title: string;
  position: number;
  href: string;
};

export type LiveTask = {
  id: string;
  instruction_md: string;
  position: number;
  kind: string;
};

export type LiveMatrixStudent = {
  sub: string;
  name: string;
  href: string;
};

export type LiveMatrixCell = {
  task_id: string;
  has_submission: boolean;
  average_score: number | null;
  score_raw?: number | null;
  score_max?: number | null;
  h5p_completed?: boolean | null;
  href: string;
};

export type LiveMatrixRow = {
  student: LiveMatrixStudent;
  tasks: LiveMatrixCell[];
};

export type LiveUnitMatrixView = {
  user: SessionBootstrapUser;
  course: LiveCourseRef;
  unit: LiveUnitRef;
  tasks: LiveTask[];
  rows: LiveMatrixRow[];
};

export type LiveDetailStudent = {
  sub: string;
  name: string;
  href: string;
};

export type LiveDetailTask = {
  id: string;
  href: string;
};

export type LiveDetailSubmission = {
  id: string;
  task_id: string;
  student_sub: string;
  instruction_md: string;
  created_at: string;
  completed_at?: string | null;
  kind: string;
  text_body?: string | null;
  feedback_md?: string | null;
  files?: Array<{ mime?: string; size?: number; url?: string }>;
};

export type LiveDetailSheetView = {
  user: SessionBootstrapUser;
  course: LiveCourseRef;
  unit: LiveUnitRef;
  student: LiveDetailStudent;
  task: LiveDetailTask;
  submission: LiveDetailSubmission | null;
};
