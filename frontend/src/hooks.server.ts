import type { Handle } from "@sveltejs/kit";

import { assertSecureFrontendSessionConfig } from "$lib/server/backend-auth";

assertSecureFrontendSessionConfig();

export const handle: Handle = async ({ event, resolve }) => {
  return await resolve(event);
};
