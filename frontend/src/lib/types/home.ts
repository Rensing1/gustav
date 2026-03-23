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
