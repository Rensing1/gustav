import type { PageServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { LearnerHome } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const home = await readTypedJsonOrNull<LearnerHome>(
    fetch,
    cookies,
    "/api/learning/views/learner-home"
  );

  return {
    home
  };
};
