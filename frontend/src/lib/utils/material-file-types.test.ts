import { describe, expect, it } from "vitest";

import {
  MATERIAL_FILE_ACCEPT,
  canonicalMaterialMime,
  isInlineMaterialMime
} from "./material-file-types";

describe("material file types", () => {
  it.each([
    ["projekt.sb3", "application/x.scratch.sb3"],
    ["programm.hex", "application/x.makecode.hex"],
    ["netz.fls", "application/x.filius.fls"],
    ["sortieren.py", "text/x-python"],
    ["daten.json", "application/json"],
    ["hinweise.txt", "text/plain"],
    ["arbeitsblatt.odt", "application/vnd.oasis.opendocument.text"],
    ["messwerte.ods", "application/vnd.oasis.opendocument.spreadsheet"],
    ["vortrag.odp", "application/vnd.oasis.opendocument.presentation"]
  ])("maps %s to its canonical MIME type", (filename, mimeType) => {
    expect(canonicalMaterialMime(filename)).toBe(mimeType);
    expect(MATERIAL_FILE_ACCEPT).toContain(filename.slice(filename.lastIndexOf(".")));
    expect(isInlineMaterialMime(mimeType)).toBe(false);
  });

  it("keeps only PDF and image files previewable", () => {
    expect(isInlineMaterialMime("application/pdf")).toBe(true);
    expect(isInlineMaterialMime("image/png")).toBe(true);
    expect(isInlineMaterialMime("image/jpeg")).toBe(true);
    expect(canonicalMaterialMime("programm.exe")).toBeNull();
  });
});
