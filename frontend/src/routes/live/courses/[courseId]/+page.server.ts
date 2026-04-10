import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseContextView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "live");

  const course = await requireBackendJson<TeacherCourseContextView>(
    fetch,
    cookies,
    `/api/teaching/views/courses/${params.courseId}/context`
  );

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Kurse",
      href: "/live"
    },
    {
      label: course.course.title
    }
  ];

  return {
    breadcrumbs,
    course,
    pageCopy:
      "Wähle eine zugeordnete Lerneinheit. Die Matrix selbst bleibt als eigener Live-Raum direkt erreichbar.",
    pageTitle: course.course.title
  };
};
