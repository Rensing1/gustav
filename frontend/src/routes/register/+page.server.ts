import { env } from "$env/dynamic/private";
import { fail, redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

import {
  isAllowedRegistrationEmail,
  parseAllowedRegistrationDomains,
} from "$lib/server/backend-auth";

function safeRedirectPath(value: string | null): string | null {
  if (!value || !value.startsWith("/")) {
    return null;
  }
  if (value.startsWith("//") || value.includes("..")) {
    return null;
  }
  return value;
}

export const load: PageServerLoad = async ({ url }) => {
  return {
    hidePageHeading: true,
    authLayout: true,
    redirectPath: safeRedirectPath(url.searchParams.get("redirect")),
  };
};

export const actions: Actions = {
  default: async ({ request, url }) => {
    const form = await request.formData();
    const loginHint = String(form.get("login_hint") || "").trim();
    const redirectPath = safeRedirectPath(String(form.get("redirect") || "") || url.searchParams.get("redirect"));
    const allowedDomains = parseAllowedRegistrationDomains(env.ALLOWED_REGISTRATION_DOMAINS);

    if (!loginHint) {
      return fail(400, {
        error: "invalid_email_domain",
        loginHint,
        redirectPath,
      });
    }

    if (!isAllowedRegistrationEmail(loginHint, allowedDomains)) {
      return fail(400, {
        error: "invalid_email_domain",
        loginHint,
        redirectPath,
      });
    }

    const params = new URLSearchParams({ login_hint: loginHint });
    if (redirectPath) {
      params.set("redirect", redirectPath);
    }
    throw redirect(303, `/auth/register?${params.toString()}`);
  },
};
