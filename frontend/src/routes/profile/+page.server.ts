import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import { backendRequest, requireBackendJson } from "$lib/server/api";
import { currentPath, requireParentSessionBootstrap } from "$lib/server/guards";
import { readFreshTokenSession } from "$lib/server/session";
import type { BreadcrumbItem } from "$lib/types/navigation";
import type { AppProfileCliToken, AppProfileView } from "$lib/types/profile";

export const load: PageServerLoad = async ({ fetch, cookies, parent, url }) => {
  const authRedirectPath = currentPath(url);
  await requireParentSessionBootstrap(parent, authRedirectPath);

  const profile = await requireBackendJson<AppProfileView>(
    fetch,
    cookies,
    "/api/app/profile",
    { authRedirectPath }
  );
  const cliTokens = await requireBackendJson<AppProfileCliToken[]>(
    fetch,
    cookies,
    "/api/app/profile/cli-tokens",
    { authRedirectPath }
  );

  const breadcrumbs: BreadcrumbItem[] = [{ label: "Profil" }];

  return {
    breadcrumbs,
    profile,
    cliTokens,
    hidePageHeading: true,
    pageTitle: "Profil",
    pageCopy: "",
    saved: url.searchParams.get("saved")
  };
};

export const actions: Actions = {
  displayName: async ({ fetch, cookies, request, url }) => {
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
      authRedirectPath: currentPath(url),
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

  name: async ({ fetch, cookies, request, url }) => {
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
      authRedirectPath: currentPath(url),
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
  },

  createCliToken: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const label = String(form.get("label") ?? "").trim();
    const scopes = form.getAll("scopes").map((scope) => String(scope));

    if (!label || scopes.length === 0) {
      return fail(400, {
        createCliToken: {
          error: "Bitte gib einen Namen und mindestens einen Scope an."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, "/api/app/profile/cli-tokens", {
      method: "POST",
      authRedirectPath: currentPath(url),
      includeSameOrigin: true,
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({ label, scopes, ttl_days: 30 })
    });

    if (!response.ok) {
      return fail(response.status, {
        createCliToken: {
          error: "Das CLI-Token konnte nicht erstellt werden."
        }
      });
    }

    const body = await response.json();
    return {
      createCliToken: {
        token: String(body.token ?? "")
      }
    };
  },

  revokeCliToken: async ({ fetch, cookies, request, url }) => {
    const form = await request.formData();
    const tokenId = String(form.get("token_id") ?? "").trim();

    if (!tokenId) {
      return fail(400, {
        revokeCliToken: {
          error: "Das CLI-Token konnte nicht gefunden werden."
        }
      });
    }

    const response = await backendRequest(fetch, cookies, `/api/app/profile/cli-tokens/${tokenId}`, {
      method: "DELETE",
      authRedirectPath: currentPath(url),
      includeSameOrigin: true
    });

    if (!response.ok) {
      return fail(response.status, {
        revokeCliToken: {
          error: "Das CLI-Token konnte nicht widerrufen werden."
        }
      });
    }

    throw redirect(303, "/profile?saved=cli-token-revoked");
  }
};
