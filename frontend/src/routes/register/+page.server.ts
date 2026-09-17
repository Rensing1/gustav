import { redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = ({ url }) => {
  const target = url.searchParams.get("redirect") || "/";
  throw redirect(303, `/auth/register?redirect=${encodeURIComponent(target)}`);
};
