import { fail } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";

type Portfolio = {
  course: { id: string; title: string; subject?: string | null; grade_level?: string | null; school_year_start?: number | null };
  submissions: Array<{
    id: string; kind: string; created_at: string; completed_at?: string | null;
    text_body?: string | null; feedback_md?: string | null; analysis_json?: Record<string, unknown> | null;
    file_name?: string | null; file_href?: string | null; task_snapshot: Record<string, unknown>;
  }>;
  export_href: string;
  latest_export?: { id: string; status: string; download_href?: string | null; error_code?: string | null } | null;
};

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "learning");
  const portfolio = await requireBackendJson<Portfolio>(
    fetch, cookies, `/api/learning/courses/${params.courseId}/portfolio`, { authRedirectPath }
  );
  return {
    breadcrumbs: [{ label: "Lernraum", href: "/learning" }, { label: portfolio.course.title }],
    hidePageHeading: true,
    pageTitle: portfolio.course.title,
    portfolio,
  };
};

export const actions: Actions = {
  export: async ({ fetch, cookies, params, url }) => {
    const response = await backendRequest(fetch, cookies, `/api/learning/courses/${params.courseId}/exports`, {
      method: "POST", includeSameOrigin: true, authRedirectPath: currentPath(url)
    });
    if (!response.ok) return fail(response.status, { exportError: "Der Export konnte nicht gestartet werden." });
    return { exportJob: await response.json() as { id: string; status: string } };
  }
};
