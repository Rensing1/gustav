import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { TeacherCourseListView } from "$lib/types/home";
import type { BreadcrumbItem } from "$lib/types/navigation";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const status = url.searchParams.get("status") === "archived" ? "archived" : "active";
  const query = (url.searchParams.get("q") ?? "").trim();
  const subject = (url.searchParams.get("subject") ?? "").trim();
  const schoolYear = (url.searchParams.get("school_year_start") ?? "").trim();
  const params = new URLSearchParams({ limit: "100", offset: "0", status });
  if (query) params.set("query", query);
  if (subject) params.set("subject", subject);
  if (schoolYear) params.set("school_year_start", schoolYear);
  const courseList = await requireBackendJson<TeacherCourseListView>(
    fetch,
    cookies,
    `/api/teaching/views/courses?${params.toString()}`,
    { authRedirectPath }
  );
  const breadcrumbs: BreadcrumbItem[] = [{ label: "Kurse" }];

  return {
    breadcrumbs,
    courses: courseList.courses,
    filters: {
      query: courseList.query,
      schoolYearStart: courseList.school_year_start,
      subject: courseList.subject,
    },
    hidePageHeading: true,
    pageCopy: null,
    showCreateDialog: url.searchParams.get("create") == "1",
    pageTitle: "Kurse",
    status: courseList.status,
    wideWorkspaceShell: true,
  };
};

export const actions: Actions = {
  createCourse: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const title = String(form.get("title") || "").trim();
    const subject = String(form.get("subject") || "").trim();
    const gradeLevel = String(form.get("grade_level") || "").trim();
    const term = String(form.get("term") || "").trim();
    const schoolYearRaw = String(form.get("school_year_start") || "").trim();
    const schoolYearStart = Number.parseInt(schoolYearRaw, 10);

    if (!title || !subject || !gradeLevel || !Number.isInteger(schoolYearStart)) {
      return fail(400, {
        createCourse: {
          error: "Bitte fülle Titel, Fach, Jahrgang und Schuljahr vollständig aus.",
          values: {
            title,
            subject,
            gradeLevel,
            term,
            schoolYearStart: schoolYearRaw,
          }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/teaching/courses", {
      method: "POST",
      authRedirectPath: currentPath(url),
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        title,
        subject: subject || null,
        grade_level: gradeLevel || null,
        term: term || null,
        school_year_start: schoolYearStart
      })
    });

    if (!response.ok) {
      let errorMessage = "Der Kurs konnte gerade nicht erstellt werden.";

      try {
        const payload = (await response.json()) as { detail?: string };
        if (response.status === 400 && payload.detail === "invalid_input") {
          errorMessage = "Bitte prüfe Titel und Kursmetadaten.";
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
            term,
            schoolYearStart: schoolYearRaw,
          }
        }
      });
    }

    const created = (await response.json()) as { id: string };
    throw redirect(303, `/teaching/courses?created=${encodeURIComponent(created.id)}`);
  },
  archiveSelected: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const courseIds = form.getAll("course_ids").map(String).filter(Boolean);
    if (!courseIds.length) {
      return fail(400, { archiveSelected: { error: "Wähle mindestens einen Kurs aus." } });
    }
    const response = await backendRequest(fetch, cookies, "/api/teaching/courses/archive-batch", {
      method: "POST",
      authRedirectPath: currentPath(url),
      includeSameOrigin: true,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ course_ids: courseIds })
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string };
      const error = payload.detail === "course_metadata_incomplete"
        ? "Vervollständige zuerst die Metadaten aller ausgewählten Kurse."
        : "Die ausgewählten Kurse konnten nicht archiviert werden.";
      return fail(response.status, { archiveSelected: { error } });
    }
    throw redirect(303, "/teaching/courses?status=archived");
  },
  restoreCourse: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const courseId = String(form.get("course_id") || "");
    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${encodeURIComponent(courseId)}/restore`, {
      method: "POST", authRedirectPath: currentPath(url), includeSameOrigin: true
    });
    if (!response.ok) {
      return fail(response.status, { restoreCourse: { error: "Der Kurs konnte nicht wiederhergestellt werden." } });
    }
    throw redirect(303, "/teaching/courses");
  }
};
