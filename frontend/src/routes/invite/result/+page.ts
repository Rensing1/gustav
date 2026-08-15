import type { PageLoad } from "./$types";

export const load: PageLoad = ({ url }) => ({
  reason: ["removed", "temporary"].includes(url.searchParams.get("reason") || "")
    ? url.searchParams.get("reason")
    : "invalid"
});
