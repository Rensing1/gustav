import type { PageServerLoad } from "./$types";

import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseContextView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const home = await requireBackendJson<TeacherCourseContextView>(
    fetch,
    cookies,
    `/api/teaching/views/courses/${params.courseId}/context`
  );

  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: "Kurse",
      href: "/teaching/courses"
    },
    {
      label: home.course.title
    }
  ];

  return {
    breadcrumbs,
    home,
    pageCopy: "Mitglieder, Einheiten und Diagnostik bleiben aus dem Kurskontext direkt erreichbar.",
    pageTitle: home.course.title
  };
};
