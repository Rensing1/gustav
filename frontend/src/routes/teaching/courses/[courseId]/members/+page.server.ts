import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseContextView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const home = await requireBackendJson<TeacherCourseContextView>(
    fetch,
    cookies,
    `/api/teaching/views/courses/${params.courseId}/context`,
    { authRedirectPath }
  );

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Kurse",
      href: "/teaching/courses"
    },
    {
      label: home.course.title,
      href: home.course.href
    },
    {
      label: "Mitglieder"
    }
  ];

  return {
    breadcrumbs,
    home,
    pageCopy: "Mitgliedschaft bleibt als eigene ruhige Detailfläche innerhalb des Kurskontexts erreichbar.",
    pageTitle: "Mitglieder"
  };
};
