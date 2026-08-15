import type { LayoutServerLoad } from "./$types";

/** Keep capability-bearing invitation pages out of browser caches and referrers. */
export const load: LayoutServerLoad = ({ setHeaders }) => {
  setHeaders({
    "cache-control": "private, no-store",
    "referrer-policy": "no-referrer"
  });

  return {};
};
