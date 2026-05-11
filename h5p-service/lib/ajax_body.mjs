/**
 * Normalize H5P ajax request bodies before delegating to Lumi.
 *
 * Why:
 *   The upstream H5P editor uses jQuery form encoding for some actions. With
 *   Express' conservative urlencoded parser (`extended: false`), array fields
 *   arrive as `libraries[]` instead of `libraries`. Lumi expects `libraries`.
 */
export function normalizeH5PAjaxBody(body) {
  if (!body || typeof body !== "object") return body;
  if (Object.prototype.hasOwnProperty.call(body, "libraries")) return body;
  if (!Object.prototype.hasOwnProperty.call(body, "libraries[]")) return body;

  const rawLibraries = body["libraries[]"];
  const libraries = Array.isArray(rawLibraries) ? rawLibraries : [rawLibraries];
  return { ...body, libraries };
}
