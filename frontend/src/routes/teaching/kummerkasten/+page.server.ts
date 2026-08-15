import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherConcernBoxView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const scope = url.searchParams.get("scope") === "archived" ? "archived" : "open";
  const concernBox = await requireBackendJson<TeacherConcernBoxView>(
    fetch,
    cookies,
    `/api/teaching/views/concern-box?scope=${encodeURIComponent(scope)}`,
    { authRedirectPath }
  );

  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Kurse", href: "/teaching/courses" },
    { label: "Kummerkasten" }
  ];

  return {
    breadcrumbs,
    concernBox,
    hidePageHeading: true,
    pageTitle: "Kummerkasten",
    pageCopy: "",
    workspaceLayout: "compact"
  };
};

export const actions: Actions = {
  archive: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const entryId = String(form.get("entry_id") ?? "").trim();
    const scope = url.searchParams.get("scope") === "archived" ? "archived" : "open";

    if (!entryId) {
      return fail(400, { archive: { error: "Es wurde kein Beitrag ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/concern-box/entries/${encodeURIComponent(entryId)}/archive`, {
      method: "POST",
      authRedirectPath: currentPath(url),
      includeSameOrigin: true
    });

    if (!response.ok && response.status !== 204) {
      return fail(response.status, { archive: { error: "Der Beitrag konnte nicht archiviert werden." } });
    }

    throw redirect(303, `/teaching/kummerkasten?scope=${encodeURIComponent(scope)}`);
  },
  restore: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const entryId = String(form.get("entry_id") ?? "").trim();

    if (!entryId) {
      return fail(400, { restore: { error: "Es wurde kein Beitrag ausgewählt." } });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/concern-box/entries/${encodeURIComponent(entryId)}/restore`, {
      method: "POST",
      authRedirectPath: currentPath(url),
      includeSameOrigin: true
    });

    if (!response.ok && response.status !== 204) {
      return fail(response.status, { restore: { error: "Der Beitrag konnte nicht wiederhergestellt werden." } });
    }

    throw redirect(303, "/teaching/kummerkasten?scope=archived");
  }
};
