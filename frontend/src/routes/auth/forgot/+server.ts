import type { RequestHandler } from "./$types";

import { startForgotFlow } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => startForgotFlow(event);
