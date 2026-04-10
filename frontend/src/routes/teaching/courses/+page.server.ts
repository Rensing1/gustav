import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseListView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const courseList = await requireBackendJson<TeacherCourseListView>(
    fetch,
    cookies,
    "/api/teaching/views/courses?limit=25&offset=0"
  );
  const breadcrumbs: BreadcrumbItem[] = [{ label: "Kurse" }];

  return {
    breadcrumbs,
    courses: courseList.courses,
    headerAction: {
      href: "/teaching/courses?create=1",
      label: "Kurs erstellen"
    },
    hidePageHeading: true,
    pageCopy:
      "Deine Kurse stehen direkt bereit. Mitglieder, Lerneinheiten und Diagnostik bleiben schnell erreichbar.",
    showCreateDialog: url.searchParams.get("create") == "1",
    pageTitle: "Kurse"
  };
};

export const actions: Actions = {
  default: async ({ fetch, cookies, request }) => {
    const form = await request.formData();
    const title = String(form.get("title") || "").trim();
    const subject = String(form.get("subject") || "").trim();
    const gradeLevel = String(form.get("grade_level") || "").trim();
    const term = String(form.get("term") || "").trim();

    if (!title) {
      return fail(400, {
        createCourse: {
          error: "Bitte gib einen Kurstitel ein.",
          values: {
            title,
            subject,
            gradeLevel,
            term
          }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/teaching/courses", {
      method: "POST",
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        title,
        subject: subject || null,
        grade_level: gradeLevel || null,
        term: term || null
      })
    });

    if (!response.ok) {
      let errorMessage = "Der Kurs konnte gerade nicht erstellt werden.";

      try {
        const payload = (await response.json()) as { detail?: string };
        if (response.status === 400 && payload.detail === "invalid_input") {
          errorMessage = "Bitte pruefe Titel und optionale Metadaten.";
        }
      } catch {
        // Ignore malformed error bodies and keep the generic message.
      }

      return fail(response.status, {
        createCourse: {
          error: errorMessage,
          values: {
            title,
            subject,
            gradeLevel,
            term
          }
        }
      });
    }

    const created = (await response.json()) as { id: string };
    throw redirect(303, `/teaching/courses?created=${encodeURIComponent(created.id)}`);
  }
};
