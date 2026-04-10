import type { RequestHandler } from "./$types";

import { startPasswordFlow } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => startPasswordFlow(event);
