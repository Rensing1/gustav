import { redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

import type { SessionBootstrap } from "$lib/types/session-bootstrap";

function safeRedirectPath(value: string | null): string | null {
  if (!value || !value.startsWith("/")) {
    return null;
  }
  if (value.startsWith("//") || value.includes("..")) {
    return null;
  }
  return value;
}

export const load: PageServerLoad = async ({ parent, url }) => {
  const { bootstrap } = (await parent()) as { bootstrap: SessionBootstrap | null };

  if (bootstrap) {
    throw redirect(303, bootstrap.start_target);
  }

  const redirectPath = safeRedirectPath(url.searchParams.get("redirect"));
  const reason = url.searchParams.get("reason") || null;

  return {
    hidePageHeading: true,
    authLayout: true,
    redirectPath,
    reason,
  };
};
