import type { Actions, PageServerLoad } from "./$types";

import { BackendRequestError, backendRequest, requireBackendJson } from "$lib/server/api";
import { splitCourseInviteRecipients } from "$lib/server/course-invite-recipients";
import { currentPath, requireParentSpaceBootstrap } from "$lib/server/guards";
import type { BreadcrumbItem } from "$lib/types/navigation";
import type { Cookies } from "@sveltejs/kit";
import { fail, redirect } from "@sveltejs/kit";

type Course = {
  id: string;
  title: string;
  subject: string | null;
  grade_level: string | null;
  term: string | null;
  school_year_start: number | null;
  status: "active" | "archived" | "deleting";
  metadata_complete: boolean;
};

type DeletionImpact = {
  course_id: string; title: string; members_count: number; submissions_count: number;
  dialogs_count: number; files_count: number;
};

type CourseMember = {
  sub: string;
  name: string;
  joined_at: string;
};

type CourseInvitation = {
  id: string;
  course_id: string;
  invite_url: string;
  expires_at: string;
  created_at: string;
  redemption_count: number;
  email_status: { pending: number; sent: number; failed: number };
};

type CourseInvitationMailStatus = CourseInvitation["email_status"] & {
  failed_recipients: string[];
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
  authRedirectPath: string
) {
  const course = await requireBackendJson<Course>(
    fetch,
    cookies,
    `/api/teaching/courses/${courseId}`,
    { authRedirectPath }
  );
  const members = await requireBackendJson<CourseMember[]>(
    fetch,
    cookies,
    `/api/teaching/courses/${courseId}/members?limit=200&offset=0`,
    { authRedirectPath }
  );
  const modules = await requireBackendJson<CourseModule[]>(
    fetch,
    cookies,
    `/api/teaching/courses/${courseId}/modules`,
    { authRedirectPath }
  );
  const units = await requireBackendJson<TeachingUnitListItem[]>(
    fetch,
    cookies,
    "/api/teaching/units?limit=100&offset=0",
    { authRedirectPath }
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

export const load: PageServerLoad = async ({ fetch, cookies, params, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSpaceBootstrap(parent, authRedirectPath, "teaching");

  const workspace = await loadCourseWorkspace(fetch, cookies, params.courseId, authRedirectPath);
  const deletionImpact = url.searchParams.get("course") == "1"
    ? await requireBackendJson<DeletionImpact>(fetch, cookies, `/api/teaching/courses/${params.courseId}/deletion-impact`, { authRedirectPath })
    : null;
  const memberSearchQuery = (url.searchParams.get("member-q") ?? "").trim();
  let memberSearchResults: DirectoryStudent[] = [];
  let invitation: CourseInvitation | null = null;
  let invitationFailedRecipients: string[] = [];

  if (url.searchParams.get("invite") == "1") {
    const invitationResponse = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/courses/${params.courseId}/invitations/active`,
      { authRedirectPath }
    );
    if (invitationResponse.status === 404) {
      invitation = null;
    } else if (!invitationResponse.ok) {
      throw new BackendRequestError(invitationResponse);
    } else {
      invitation = await invitationResponse.json() as CourseInvitation;
      const statusResponse = await backendRequest(
        fetch,
        cookies,
        `/api/teaching/courses/${params.courseId}/invitations/${invitation.id}/email-deliveries/status`,
        { authRedirectPath }
      );
      if (!statusResponse.ok) {
        throw new BackendRequestError(statusResponse);
      }
      const status = await statusResponse.json() as CourseInvitationMailStatus;
      invitation.email_status = {
        pending: status.pending,
        sent: status.sent,
        failed: status.failed
      };
      invitationFailedRecipients = status.failed_recipients;
    }
  }

  if (url.searchParams.get("add-member") == "1" && memberSearchQuery.length >= 2) {
    const candidates = await requireBackendJson<DirectoryStudent[]>(
      fetch,
      cookies,
      `/api/users/search?role=student&limit=8&q=${encodeURIComponent(memberSearchQuery)}`,
      { authRedirectPath }
    );
    const attachedMemberSubs = new Set(workspace.members.map((member) => member.sub));
    memberSearchResults = candidates.filter((candidate) => !attachedMemberSubs.has(candidate.sub));
  }

  return {
    assignedUnits: workspace.assignedUnits,
    availableUnits: workspace.availableUnits,
    breadcrumbs: [] as BreadcrumbItem[],
    course: workspace.course,
    deletionImpact,
    hidePageHeading: true,
    invitation,
    invitationFailedRecipients,
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
    showInviteDrawer: url.searchParams.get("invite") == "1",
    showMembersDrawer: url.searchParams.get("members") == "1",
    workspaceLayout: "wide",
  };
};

export const actions: Actions = {
  createInvitation: async ({ fetch, cookies, params, url }) => {
    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/courses/${params.courseId}/invitations`,
      {
        method: "POST",
        includeSameOrigin: true,
        authRedirectPath: currentPath(url)
      }
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string };
      return fail(response.status, {
        createInvitation: {
          error: payload.detail === "course_metadata_incomplete"
            ? "Vervollständige zuerst Fach, Jahrgang und Schuljahr."
            : "Der Klassenlink konnte nicht erstellt werden."
        }
      });
    }
    throw redirect(303, `/teaching/courses/${params.courseId}?invite=1`);
  },
  revokeInvitation: async ({ fetch, cookies, params, request, url }) => {
    const invitationId = String((await request.formData()).get("invitation_id") ?? "").trim();
    if (!invitationId) return fail(400, { revokeInvitation: { error: "Die Einladung fehlt." } });
    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/courses/${params.courseId}/invitations/${encodeURIComponent(invitationId)}`,
      { method: "DELETE", includeSameOrigin: true, authRedirectPath: currentPath(url) }
    );
    if (!response.ok) {
      return fail(response.status, { revokeInvitation: { error: "Der Link konnte nicht widerrufen werden." } });
    }
    throw redirect(303, `/teaching/courses/${params.courseId}?invite=1`);
  },
  sendInvitationEmails: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const invitationId = String(formData.get("invitation_id") ?? "").trim();
    const recipients = String(formData.get("recipients") ?? "").trim();
    if (!invitationId || !recipients) {
      return fail(400, { sendInvitationEmails: { error: "Gib mindestens eine Schul-E-Mail-Adresse ein." } });
    }
    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/courses/${params.courseId}/invitations/${encodeURIComponent(invitationId)}/email-deliveries`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ recipients: splitCourseInviteRecipients(recipients) }),
        includeSameOrigin: true,
        authRedirectPath: currentPath(url)
      }
    );
    if (!response.ok) {
      return fail(response.status, {
        sendInvitationEmails: { error: "Prüfe die Adressen und die zugelassenen Schul-Domains." }
      });
    }
    throw redirect(303, `/teaching/courses/${params.courseId}?invite=1`);
  },
  retryInvitationEmails: async ({ fetch, cookies, params, request, url }) => {
    const invitationId = String((await request.formData()).get("invitation_id") ?? "").trim();
    if (!invitationId) return fail(400, { retryInvitationEmails: { error: "Die Einladung fehlt." } });
    const response = await backendRequest(
      fetch,
      cookies,
      `/api/teaching/courses/${params.courseId}/invitations/${encodeURIComponent(invitationId)}/email-deliveries/retry`,
      { method: "POST", includeSameOrigin: true, authRedirectPath: currentPath(url) }
    );
    if (!response.ok) {
      return fail(response.status, { retryInvitationEmails: { error: "Der erneute Versand konnte nicht gestartet werden." } });
    }
    throw redirect(303, `/teaching/courses/${params.courseId}?invite=1`);
  },
  saveCourse: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const title = String(formData.get("title") ?? "").trim();
    const subject = String(formData.get("subject") ?? "").trim();
    const gradeLevel = String(formData.get("grade_level") ?? "").trim();
    const term = String(formData.get("term") ?? "").trim();
    const schoolYearRaw = String(formData.get("school_year_start") ?? "").trim();
    const schoolYearStart = Number.parseInt(schoolYearRaw, 10);

    if (!title || !subject || !gradeLevel || !Number.isInteger(schoolYearStart)) {
      return fail(400, {
        saveCourse: {
          error: "Titel, Fach, Jahrgang und Schuljahr sind erforderlich.",
          values: { title, subject, gradeLevel, term, schoolYearStart: schoolYearRaw }
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}`, {
      method: "PATCH",
      body: JSON.stringify({
        title,
        subject: subject || null,
        grade_level: gradeLevel || null,
        term: term || null,
        school_year_start: schoolYearStart
      }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
    });

    if (!response.ok) {
      return fail(response.status, {
        saveCourse: {
          error: "Der Kurs konnte nicht gespeichert werden.",
          values: { title, subject, gradeLevel, term, schoolYearStart: schoolYearRaw }
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}`);
  },
  deleteCourse: async ({ fetch, cookies, params, request, url }) => {
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

    const confirmed = formData.get("confirm_student_data_loss") === "yes";
    if (!confirmed) {
      return fail(400, { deleteCourse: { error: "Bestätige auch den unwiderruflichen Verlust der Schülerdaten." } });
    }
    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/deletion-jobs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ confirmation_title: confirmation, confirm_student_data_loss: true }),
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
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
  archiveCourse: async ({ fetch, cookies, params, url }) => {
    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/archive`, {
      method: "POST", includeSameOrigin: true, authRedirectPath: currentPath(url)
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string };
      return fail(response.status, { archiveCourse: { error: payload.detail === "course_metadata_incomplete" ? "Vervollständige zuerst Fach, Jahrgang und Schuljahr." : "Der Kurs konnte nicht archiviert werden." } });
    }
    throw redirect(303, `/teaching/courses/${params.courseId}`);
  },
  restoreCourse: async ({ fetch, cookies, params, url }) => {
    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/restore`, {
      method: "POST", includeSameOrigin: true, authRedirectPath: currentPath(url)
    });
    if (!response.ok) return fail(response.status, { restoreCourse: { error: "Der Kurs konnte nicht wiederhergestellt werden." } });
    throw redirect(303, `/teaching/courses/${params.courseId}`);
  },
  addMember: async ({ fetch, cookies, params, request, url }) => {
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
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
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
  removeMember: async ({ fetch, cookies, params, request, url }) => {
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
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
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
  addUnit: async ({ fetch, cookies, params, request, url }) => {
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
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
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
  removeUnit: async ({ fetch, cookies, params, request, url }) => {
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
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
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
  reorderModules: async ({ fetch, cookies, params, request, url }) => {
    const formData = await request.formData();
    const moduleIds = formData.getAll("module_ids").map((value) => String(value));

    if (!moduleIds.length) {
      return fail(400, {
        reorderModules: {
          error: "Die Reihenfolge enthält keine Lerneinheiten.",
          moduleIds
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/teaching/courses/${params.courseId}/modules/reorder`, {
      method: "POST",
      body: JSON.stringify({ module_ids: moduleIds }),
      headers: { "content-type": "application/json" },
      includeSameOrigin: true,
      authRedirectPath: currentPath(url)
    });

    if (!response.ok) {
      return fail(response.status, {
        reorderModules: {
          error: "Die Reihenfolge konnte nicht gespeichert werden.",
          moduleIds
        }
      });
    }

    throw redirect(303, `/teaching/courses/${params.courseId}`);
  }
};
