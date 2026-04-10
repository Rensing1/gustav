import { redirect } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";

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
  default: async ({ request }) => {
    const form = await request.formData();
    const loginHint = String(form.get("login_hint") || "").trim();
    const params = new URLSearchParams();

    if (loginHint) {
      params.set("login_hint", loginHint);
    }

    const target = params.size ? `/auth/forgot?${params.toString()}` : "/auth/forgot";
    throw redirect(303, target);
  },
};
