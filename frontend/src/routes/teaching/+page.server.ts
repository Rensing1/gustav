import type { PageServerLoad } from "./$types";

import { readTypedJsonOrNull } from "$lib/server/api";
import type { TeacherHome } from "$lib/types/home";

export const load: PageServerLoad = async ({ fetch, cookies }) => {
  const home = await readTypedJsonOrNull<TeacherHome>(
    fetch,
    cookies,
    "/api/teaching/views/teacher-home"
  );

  return {
    home
  };
};
