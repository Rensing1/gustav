const MATERIAL_MIME_BY_EXTENSION: Readonly<Record<string, string>> = {
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".sb3": "application/x.scratch.sb3",
  ".hex": "application/x.makecode.hex",
  ".fls": "application/x.filius.fls",
  ".py": "text/x-python",
  ".json": "application/json",
  ".txt": "text/plain",
  ".odt": "application/vnd.oasis.opendocument.text",
  ".ods": "application/vnd.oasis.opendocument.spreadsheet",
  ".odp": "application/vnd.oasis.opendocument.presentation"
};

const INLINE_MIME_TYPES = new Set(["application/pdf", "image/png", "image/jpeg"]);

export const MATERIAL_FILE_ACCEPT = Object.entries(MATERIAL_MIME_BY_EXTENSION)
  .flatMap(([extension, mimeType]) => [extension, mimeType])
  .join(",");

export const MATERIAL_FILE_FORMAT_NAMES =
  "PDF, PNG, JPEG, SB3, HEX, FLS, PY, JSON, TXT, ODT, ODS und ODP";

export function canonicalMaterialMime(filename: string): string | null {
  const normalized = filename.trim().toLowerCase();
  const dot = normalized.lastIndexOf(".");
  if (dot < 0) return null;
  return MATERIAL_MIME_BY_EXTENSION[normalized.slice(dot)] ?? null;
}

export function isInlineMaterialMime(mimeType: string | null | undefined): boolean {
  return INLINE_MIME_TYPES.has(String(mimeType ?? "").trim().toLowerCase());
}
