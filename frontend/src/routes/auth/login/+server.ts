import type { RequestHandler } from "./$types";

import { startLoginFlow } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => startLoginFlow(event);
