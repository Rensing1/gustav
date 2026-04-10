import type { RequestHandler } from "./$types";

import { handleLogout } from "$lib/server/backend-auth";

export const GET: RequestHandler = (event) => handleLogout(event);
