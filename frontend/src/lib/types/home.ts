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
