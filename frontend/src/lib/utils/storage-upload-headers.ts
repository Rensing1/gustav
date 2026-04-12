export function buildStorageUploadHeaders(
  rawHeaders: Record<string, string> | undefined,
  fallbackMimeType: string
): Headers {
  const headers = new Headers();

  if (rawHeaders) {
    for (const [key, value] of Object.entries(rawHeaders)) {
      const normalizedName = key.trim().toLowerCase();
      if (!normalizedName) {
        continue;
      }
      headers.set(normalizedName, value);
    }
  }

  const normalizedFallbackMimeType = fallbackMimeType.trim().toLowerCase();
  if (!headers.has("content-type") && normalizedFallbackMimeType) {
    headers.set("content-type", normalizedFallbackMimeType);
  }

  return headers;
}
