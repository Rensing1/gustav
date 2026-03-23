import type { RequestHandler } from "./$types";

import { proxyBackendAuthGet } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => proxyBackendAuthGet(event, "/auth/register");

