import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { LearnerConcernBoxView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  await requireParentSpaceBootstrap(parent, currentPath(url), "learning");

  const concernBox = await requireBackendJson<LearnerConcernBoxView>(
    fetch,
    cookies,
    "/api/learning/views/concern-box"
  );

  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Lernraum", href: "/learning" },
    { label: "Kummerkasten" }
  ];

  return {
    breadcrumbs,
    concernBox,
    hidePageHeading: true,
    pageTitle: "Kummerkasten",
    pageCopy: "",
    sent: url.searchParams.get("sent") === "1"
  };
};

export const actions: Actions = {
  default: async ({ fetch, cookies, request }) => {
    const form = await request.formData();
    const courseId = String(form.get("course_id") ?? "").trim();
    const messageText = String(form.get("message_text") ?? "").trim();
    const anonymous = form.get("anonymous") === "on";

    if (!courseId) {
      return fail(400, {
        submit: {
          error: "Bitte wähle einen Kurs aus.",
          values: { courseId, messageText, anonymous }
        }
      });
    }

    if (!messageText) {
      return fail(400, {
        submit: {
          error: "Bitte schreibe einen Beitrag.",
          values: { courseId, messageText, anonymous }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/learning/concern-box/entries", {
      method: "POST",
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        course_id: courseId,
        message_text: messageText,
        anonymous
      })
    });

    if (!response.ok) {
      return fail(response.status, {
        submit: {
          error: response.status === 403 ? "Du kannst nur Beiträge für eigene Kurse absenden." : "Der Beitrag konnte nicht gesendet werden.",
          values: { courseId, messageText, anonymous }
        }
      });
    }

    throw redirect(303, "/learning/kummerkasten?sent=1");
  }
};
