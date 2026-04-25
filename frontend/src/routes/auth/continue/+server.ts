import type { RequestHandler } from "./$types";

import { startContinuationFlow } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => startContinuationFlow(event);
