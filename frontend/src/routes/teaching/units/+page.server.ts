import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherUnitsCatalogView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

function pageHref(url: URL): string {
  const query = url.searchParams.toString();
  return query ? `/api/teaching/views/units/catalog?${query}` : "/api/teaching/views/units/catalog";
}

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const catalog = await requireBackendJson<TeacherUnitsCatalogView>(
    fetch,
    cookies,
    pageHref(url)
  );

  const breadcrumbs: BreadcrumbItem[] = [{ label: "Lerneinheiten" }];

  return {
    breadcrumbs,
    catalog,
    hidePageHeading: true,
    wideWorkspaceShell: true,
    pageTitle: "Lerneinheiten",
    pageCopy: ""
  };
};

export const actions: Actions = {
  default: async ({ fetch, cookies, request }) => {
    const form = await request.formData();
    const title = String(form.get("title") || "").trim();
    const summary = String(form.get("summary") || "").trim();

    if (!title) {
      return fail(400, {
        createUnit: {
          error: "Bitte gib einen Titel für die Lerneinheit ein.",
          values: { title, summary }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/teaching/units", {
      method: "POST",
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        title,
        summary: summary || null
      })
    });

    if (!response.ok) {
      return fail(response.status, {
        createUnit: {
          error: "Die Lerneinheit konnte gerade nicht erstellt werden.",
          values: { title, summary }
        }
      });
    }

    const created = (await response.json()) as { id: string };
    throw redirect(303, `/teaching/units/${created.id}`);
  }
};
