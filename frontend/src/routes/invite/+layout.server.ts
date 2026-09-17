import type { LayoutServerLoad } from "./$types";

/** Keep capability-bearing invitation pages out of browser caches and referrers. */
export const load: LayoutServerLoad = ({ setHeaders, url }) => {
  setHeaders({
    "cache-control": "private, no-store",
    "referrer-policy": url.pathname === "/invite/complete" ? "same-origin" : "no-referrer"
  });

  return {};
};
