import type { RequestHandler } from "./$types";

import { handleAuthCallback } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => handleAuthCallback(event);
