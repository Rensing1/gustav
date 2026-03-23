import type { LayoutServerLoad } from "./$types";

import { readJsonOrNull } from "$lib/server/api";

export const load: LayoutServerLoad = async ({ fetch, request }) => {
  const bootstrap = await readJsonOrNull(fetch, request, "/api/app/session-bootstrap");

  return {
    bootstrap
  };
};

