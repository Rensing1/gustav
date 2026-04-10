import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireSessionBootstrap } from "$lib/server/guards";
import { readFreshTokenSession } from "$lib/server/session";
import type { BreadcrumbItem } from "$lib/types/navigation";
import type { AppProfileView } from "$lib/types/profile";

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
  await requireSessionBootstrap(fetch, cookies, currentPath(url));

  const profile = await requireBackendJson<AppProfileView>(
    fetch,
    cookies,
    "/api/app/profile"
  );

  const breadcrumbs: BreadcrumbItem[] = [{ label: "Profil" }];

  return {
    breadcrumbs,
    profile,
    hidePageHeading: true,
    pageTitle: "Profil",
    pageCopy: "",
    saved: url.searchParams.get("saved")
  };
};

export const actions: Actions = {
  displayName: async ({ fetch, cookies, request }) => {
    const form = await request.formData();
    const displayName = String(form.get("display_name") ?? "").trim();

    if (!displayName) {
      return fail(400, {
        displayName: {
          error: "Bitte gib einen Anzeigenamen ein."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/app/profile/display-name", {
      method: "PATCH",
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({ display_name: displayName })
    });

    if (!response.ok) {
      return fail(response.status, {
        displayName: {
          error: "Der Anzeigename konnte nicht gespeichert werden."
        }
      });
    }

    await readFreshTokenSession(cookies, fetch, { forceRefresh: true });
    throw redirect(303, "/profile?saved=display-name");
  },

  name: async ({ fetch, cookies, request }) => {
    const form = await request.formData();
    const firstName = String(form.get("first_name") ?? "").trim();
    const lastName = String(form.get("last_name") ?? "").trim();

    if (!firstName && !lastName) {
      return fail(400, {
        name: {
          error: "Bitte gib einen Vor- oder Nachnamen ein."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/app/profile/name", {
      method: "PATCH",
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({ first_name: firstName, last_name: lastName })
    });

    if (!response.ok) {
      let error = "Vor- und Nachname konnten nicht gespeichert werden.";
      if (response.status === 409) {
        const body = await response.json().catch(() => null);
        const detail = body && typeof body === "object" ? String((body as Record<string, unknown>).detail ?? "") : "";
        error = detail
          ? `Vor- und Nachname sind derzeit gesperrt. Nächste Änderung ab ${detail}.`
          : "Vor- und Nachname sind derzeit gesperrt.";
      } else if (response.status >= 500 || response.status === 403) {
        error = "Die Namensänderung konnte gerade nicht an das Kontosystem übertragen werden.";
      }
      return fail(response.status, {
        name: { error }
      });
    }

    throw redirect(303, "/profile?saved=name");
  }
};
