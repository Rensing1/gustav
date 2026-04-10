import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSpaceBootstrap } from "$lib/server/guards";
import type { BreadcrumbItem } from "$lib/types/navigation";
import type { Cookies } from "@sveltejs/kit";
import { fail, redirect } from "@sveltejs/kit";

type Course = {
  id: string;
  title: string;
  subject: string | null;
  grade_level: string | null;
  term: string | null;
};

type CourseMember = {
  sub: string;
  name: string;
  joined_at: string;
};

type CourseModule = {
  id: string;
  course_id: string;
  unit_id: string;
  position: number;
};

type TeachingUnitListItem = {
  id: string;
  title: string;
  summary?: string | null;
  unit_type?: string | null;
};

type DirectoryStudent = {
  sub: string;
  name: string;
};

type CourseWorkspaceUnit = {
  id: string;
  module_id: string;
  title: string;
  position: number;
  href: string;
};

async function loadCourseWorkspace(
  fetch: typeof globalThis.fetch,
  cookies: Cookies,
  courseId: string,
) {
  const course = await requireBackendJson<Course>(
    fetch,
    cookies,
    `/api/teaching/courses/${courseId}`
  );
  const members = await requireBackendJson<CourseMember[]>(
    fetch,
    cookies,
    `/api/teaching/courses/${courseId}/members?limit=200&offset=0`
  );
  const modules = await requireBackendJson<CourseModule[]>(
    fetch,
    cookies,
    `/api/teaching/courses/${courseId}/modules`
  );
  const units = await requireBackendJson<TeachingUnitListItem[]>(
    fetch,
    cookies,
    "/api/teaching/units?limit=100&offset=0"
  );

  const unitsById = new Map(units.map((unit) => [unit.id, unit]));
  const assignedUnits: CourseWorkspaceUnit[] = modules.map((module) => {
    const unit = unitsById.get(module.unit_id);
    return {
      id: module.unit_id,
      module_id: module.id,
      title: unit?.title ?? "Unbekannte Lerneinheit",
      position: module.position,
      href: `/teaching/units/${module.unit_id}`
    };
  });

  const attachedUnitIds = new Set(modules.map((module) => module.unit_id));
  const availableUnits = units.filter((unit) => !attachedUnitIds.has(unit.id));

  return {
    assignedUnits,
    availableUnits,
    course,
    members,
    modules
  };
}

export const load: PageServerLoad = async ({ fetch, cookies, params, url }) => {
  await requireSpaceBootstrap(fetch, cookies, currentPath(url), "teaching");

  const workspace = await loadCourseWorkspace(fetch, cookies, params.courseId);
  const memberSearchQuery = (url.searchParams.get("member-q") ?? "").trim();
  let memberSearchResults: DirectoryStudent[] = [];

  if (url.searchParams.get("add-member") == "1" && memberSearchQuery.length >= 2) {
    const candidates = await requireBackendJson<DirectoryStudent[]>(
      fetch,
      cookies,
      `/api/users/search?role=student&limit=8&q=${encodeURIComponent(memberSearchQuery)}`
    );
    const attachedMemberSubs = new Set(workspace.members.map((member) => member.sub));
    memberSearchResults = candidates.filter((candidate) => !attachedMemberSubs.has(candidate.sub));
  }

  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Kurse", href: "/teaching/courses" }
  ];

  return {
    assignedUnits: workspace.assignedUnits,
    availableUnits: workspace.availableUnits,
    breadcrumbs,
    course: workspace.course,
    hidePageHeading: true,
    memberSearchQuery,
    memberSearchResults,
    members: workspace.members.map((member) => ({
      ...member,
      href: `/diagnostics/learners/${encodeURIComponent(member.sub)}`
    })),
    pageCopy: `${workspace.members.length} Mitglieder · ${workspace.assignedUnits.length} Lerneinheiten`,
    pageTitle: workspace.course.title,
    showAddMemberDialog: url.searchParams.get("add-member") == "1",
    showAddUnitDialog: url.searchParams.get("add-unit") == "1",
    showCourseDrawer: url.searchParams.get("course") == "1",
    showMembersDrawer: url.searchParams.get("members") == "1",
  };
};

export const actions: Actions = {
  saveCourse: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const title = String(formData.get("title") ?? "").trim();
    const subject = String(formData.get("subject") ?? "").trim();
    const gradeLevel = String(formData.get("grade_level") ?? "").trim();
    const term = String(formData.get("term") ?? "").trim();

    if (!title) {
      return fail(400, {
        saveCourse: {
          error: "Bitte gib einen Kurstitel ein.",
          values: { title, subject, gradeLevel, term }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}`, {
      method: "PATCH",
      body: JSON.stringify({
        title,
        subject: subject || null,
        grade_level: gradeLevel || null,
        term: term || null
      }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        saveCourse: {
          error: "Der Kurs konnte nicht gespeichert werden.",
          values: { title, subject, gradeLevel, term }
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}?members=1`);
  },
  deleteCourse: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const confirmation = String(formData.get("confirmation") ?? "").trim();
    const expectedTitle = String(formData.get("expected_title") ?? "").trim();

    if (confirmation != expectedTitle) {
      return fail(400, {
        deleteCourse: {
          error: "Bitte gib den Kurstitel exakt zur Bestätigung ein."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        deleteCourse: {
          error: "Der Kurs konnte nicht gelöscht werden."
        }
      });
    }

    throw redirect(303, "/teaching/courses");
  },
  addMember: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const studentSub = String(formData.get("student_sub") ?? "").trim();
    const query = String(formData.get("member_q") ?? "").trim();

    if (!studentSub) {
      return fail(400, {
        addMember: {
          error: "Bitte wähle einen Lernenden aus.",
          values: { query }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/members`, {
      method: "POST",
      body: JSON.stringify({ student_sub: studentSub }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok && response.status != 204) {
      return fail(response.status, {
        addMember: {
          error: "Der Lernende konnte nicht zum Kurs hinzugefügt werden.",
          values: { query }
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}?members=1`);
  },
  removeMember: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const studentSub = String(formData.get("student_sub") ?? "").trim();

    if (!studentSub) {
      return fail(400, {
        removeMember: {
          error: "Es wurde kein Mitglied zum Entfernen ausgewählt."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/members/${encodeURIComponent(studentSub)}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        removeMember: {
          error: "Das Mitglied konnte nicht entfernt werden."
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}`);
  },
  addUnit: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const unitId = String(formData.get("unit_id") ?? "").trim();

    if (!unitId) {
      return fail(400, {
        addUnit: {
          error: "Bitte wähle eine Lerneinheit aus.",
          values: { unitId }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/modules`, {
      method: "POST",
      body: JSON.stringify({ unit_id: unitId }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        addUnit: {
          error: "Die Lerneinheit konnte nicht hinzugefügt werden.",
          values: { unitId }
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}`);
  },
  removeUnit: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const moduleId = String(formData.get("module_id") ?? "").trim();

    if (!moduleId) {
      return fail(400, {
        removeUnit: {
          error: "Es wurde keine Lerneinheit zum Entfernen ausgewählt."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/modules/${moduleId}`, {
      method: "DELETE",
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        removeUnit: {
          error: "Die Lerneinheit konnte nicht entfernt werden."
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}`);
  },
  reorderModules: async ({ fetch, cookies, params, request }) => {
    const formData = await request.formData();
    const moduleIds = formData.getAll("module_ids").map((value) => String(value));

    if (!moduleIds.length) {
      return fail(400, {
        reorderModules: {
          error: "Die Reihenfolge enthält keine Lerneinheiten."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/modules/reorder`, {
      method: "POST",
      body: JSON.stringify({ module_ids: moduleIds }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        reorderModules: {
          error: "Die Reihenfolge konnte nicht gespeichert werden."
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}`);
  }
};
