import type { RequestHandler } from "./$types";

import { startRegisterFlow } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => startRegisterFlow(event);
