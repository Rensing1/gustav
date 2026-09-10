import type { PageLoad } from "./$types";

/** Use the public auth frame; invitation capabilities remain browser-only. */
export const load: PageLoad = () => ({ authLayout: true });
