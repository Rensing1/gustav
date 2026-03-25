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
