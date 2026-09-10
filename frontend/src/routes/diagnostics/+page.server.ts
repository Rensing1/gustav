import type { PageServerLoad } from "./$types";
import { requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseListView } from "$lib/types/home";

export const load: PageServerLoad = async ({ parent, url, fetch, cookies }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "diagnostics");
  const courses: TeacherCourseListView["courses"] = [];
  // Use the existing paginated, owner-scoped list; no second catalogue endpoint.
  for (let offset = 0; ; offset += 100) {
    const page = await requireBackendJson<TeacherCourseListView>(
      fetch, cookies, `/api/teaching/views/courses?status=active&limit=100&offset=${offset}`, { authRedirectPath }
    );
    courses.push(...page.courses);
    if (page.courses.length < 100) break;
  }
  return { courses, workspaceLayout: "compact", hidePageHeading: true, pageTitle: "Diagnostik" };
};
