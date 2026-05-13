import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import { BackendRequestError, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearnerHome } from "$lib/types/home";
import type { LearningCoursePageData, LearningCourseUnit } from "$lib/types/learning";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  try {
    const authRedirectPath = currentPath(url);
    const bootstrap = await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");
    const [units, home] = await Promise.all([
      requireBackendJson<LearningCourseUnit[]>(
        fetch,
        cookies,
        `/api/learning/courses/${encodeURIComponent(params.courseId)}/units`,
        { authRedirectPath }
      ),
      requireBackendJson<LearnerHome>(
        fetch,
        cookies,
        "/api/learning/views/learner-home",
        { authRedirectPath }
      )
    ]);

    const courseTitle =
      home.courses.find((course) => course.id === params.courseId)?.title ?? "Kursraum";
    const breadcrumbs: BreadcrumbItem[] = [
      { label: "Lernraum", href: "/learning" },
      { label: courseTitle }
    ];

    const pageData = {
      user: bootstrap.user,
      courseId: params.courseId,
      courseTitle,
      units
    } satisfies LearningCoursePageData;

    return {
      ...pageData,
      breadcrumbs,
      hidePageHeading: true,
      pageTitle: courseTitle
    };
  } catch (caught) {
    if (caught instanceof BackendRequestError) {
      throw error(caught.response.status, "Lernkurs konnte nicht geladen werden.");
    }
    throw caught;
  }
};
