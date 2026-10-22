import type { PageLoad } from "./$types";

export const load: PageLoad = () => ({
  hidePageHeading: true,
  authLayout: true,
});
