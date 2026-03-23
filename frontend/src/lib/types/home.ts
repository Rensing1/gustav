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
