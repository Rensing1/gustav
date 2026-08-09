import type { SessionBootstrapUser } from "$lib/types/session-bootstrap";

export type LearnerHomeCourse = {
  id: string;
  title: string;
  href: string;
  school_year_start: number | null;
};

export type LearnerHome = {
  user: SessionBootstrapUser;
  current_courses: LearnerHomeCourse[];
  past_courses: LearnerHomeCourse[];
};

export type ConcernBoxCourseOption = {
  id: string;
  title: string;
};

export type LearnerConcernBoxView = {
  user: SessionBootstrapUser;
  courses: ConcernBoxCourseOption[];
};

export type TeacherHomeCourseOption = {
  id: string;
  title: string;
};

export type TeacherHomeRecentUnit = {
  id: string;
  title: string;
  updated_at: string;
  href: string;
};

export type TeacherHome = {
  user: SessionBootstrapUser;
  courses: TeacherHomeCourseOption[];
  recent_units: TeacherHomeRecentUnit[];
  units_href: string;
  create_unit_href: string;
};

export type TeacherConcernBoxFilterOption = {
  id: "open" | "archived";
  label: string;
  active: boolean;
};

export type TeacherConcernBoxEntry = {
  id: string;
  course_id: string;
  course_title: string;
  message_text: string;
  anonymous: boolean;
  student_name: string | null;
  created_at: string;
  archived_at: string | null;
};

export type TeacherConcernBoxView = {
  user: SessionBootstrapUser;
  scopes: TeacherConcernBoxFilterOption[];
  active_scope: "open" | "archived";
  entries: TeacherConcernBoxEntry[];
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
  school_year_start: number | null;
  status: "active" | "archived";
  metadata_complete: boolean;
  archived_at: string | null;
};

export type TeacherCourseListView = {
  user: SessionBootstrapUser;
  status: "active" | "archived";
  query: string;
  school_year_start: number | null;
  subject: string;
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

export type LiveCourseUnitsView = {
  user: SessionBootstrapUser;
  course: {
    id: string;
    title: string;
    href: string;
  };
  units: Array<{
    id: string;
    title: string;
    position: number;
    href: string;
  }>;
};

export type TeacherUnitsCatalogCourse = {
  id: string;
  title: string;
  href: string;
};

export type TeacherUnitsCatalogItem = {
  id: string;
  title: string;
  topic?: string | null;
  status_label: string;
  status_tone: "accent" | "success" | "muted";
  courses_count: number;
  courses: TeacherUnitsCatalogCourse[];
  updated_at: string;
  href: string;
};

export type TeacherUnitsCatalogView = {
  user: SessionBootstrapUser;
  query: string;
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
  kind: "markdown" | "file" | "simulation";
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
  kind: "native" | "h5p" | "visual" | "scratch" | "calliope" | "filius" | "dialog";
  h5p?: {
    content_id?: string | null;
    display_options?: Record<string, unknown> | null;
  } | null;
  visual?: Record<string, never> | null;
  scratch?: Record<string, never> | null;
  calliope?: Record<string, never> | null;
  filius?: Record<string, never> | null;
  dialog?: {
    partner_name: string;
    partner_description_md: string;
    role_md: string;
    learning_goal_md: string;
    opening_message_md: string;
    response_mode: "free_text" | "hybrid";
    max_rounds: number;
    closing_prompt_md?: string | null;
  } | null;
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

export type LiveSummaryStudent = {
  sub: string;
  name: string;
};

export type LiveSummaryCell = {
  task_id: string;
  has_submission: boolean;
  average_score: number | null;
  created_at?: string | null;
  score_raw?: number | null;
  score_max?: number | null;
  h5p_completed?: boolean | null;
};

export type LiveSummaryRow = {
  student: LiveSummaryStudent;
  tasks: LiveSummaryCell[];
};

export type LiveSummaryPayload = {
  cursor: string;
  tasks: LiveTask[];
  rows: LiveSummaryRow[];
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
  created_at?: string | null;
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

export type LiveDashboardLatestSubmission = {
  task_id: string;
  task_position: number;
  task_label: string;
  created_at: string;
  average_score: number | null;
} | null;

export type LiveUnitDashboardRow = {
  student: LiveMatrixStudent;
  progress_percent: number;
  average_score: number | null;
  latest_submission: LiveDashboardLatestSubmission;
  href: string;
};

export type LiveStudentPanelTask = {
  task_id: string;
  task_position: number;
  task_label: string;
  has_submission: boolean;
  average_score: number | null;
  is_latest_submission: boolean;
  href: string;
};

export type LiveStudentPanelView = {
  student: LiveDetailStudent;
  tasks: LiveStudentPanelTask[];
  selected_task_id: string | null;
  selected_task_detail: LiveDetailSubmission | null;
} | null;

export type LiveUnitDashboardView = {
  user: SessionBootstrapUser;
  course: LiveCourseRef;
  unit: LiveUnitRef;
  summary: {
    learners_count: number;
    tasks_count: number;
    completion_rate_percent: number;
    average_score: number | null;
  };
  rows: LiveUnitDashboardRow[];
  selected_student_panel: LiveStudentPanelView;
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

export type LiveDialogTranscript = {
  id: string;
  status: "completed";
  round_count: number;
  dialog: {
    partner_name: string;
    partner_description_md: string;
    opening_message_md: string;
    response_mode: "free_text" | "hybrid";
    max_rounds: number;
    closing_prompt_md?: string | null;
  };
  turns: Array<{
    id: string;
    round_nr: number;
    student_message_md: string;
    used_sentence_starter_md?: string | null;
    used_sentence_starter_source?: string | null;
    assistant_reply_md: string;
  }>;
  closing_answer_md?: string | null;
};

export type LiveDetailSubmission = {
  id: string;
  task_id: string;
  student_sub: string;
  instruction_md: string;
  created_at: string;
  completed_at?: string | null;
  kind: string;
  score_raw?: number | null;
  score_max?: number | null;
  h5p?: {
    content_id?: string | null;
    review_token?: string | null;
  } | null;
  text_body?: string | null;
  feedback_md?: string | null;
  analysis_json?: {
    schema: string;
    score?: number | null;
    text?: string | null;
    criteria_results?: Array<{
      criterion: string;
      score?: number | null;
      max_score?: number | null;
      explanation_md?: string | null;
    }>;
  } | null;
  files?: Array<{ mime?: string; size?: number; url?: string }>;
  dialog?: LiveDialogTranscript | null;
};

export type LiveDetailSheetView = {
  user: SessionBootstrapUser;
  course: LiveCourseRef;
  unit: LiveUnitRef;
  student: LiveDetailStudent;
  task: LiveDetailTask;
  submission: LiveDetailSubmission | null;
};
