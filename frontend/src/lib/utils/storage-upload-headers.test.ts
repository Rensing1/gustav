import { describe, expect, it } from "vitest";

import { buildStorageUploadHeaders } from "./storage-upload-headers";

describe("buildStorageUploadHeaders", () => {
  it("collapses content-type casing variants into one lowercase header", () => {
    const headers = buildStorageUploadHeaders(
      {
        "content-type": "application/pdf",
        "Content-Type": "application/pdf"
      },
      "application/pdf"
    );

    const contentTypeEntries = Array.from(headers.entries()).filter(([key]) => key === "content-type");

    expect(contentTypeEntries).toEqual([["content-type", "application/pdf"]]);
    expect(headers.get("content-type")).toBe("application/pdf");
  });

  it("keeps non-content-type headers unchanged", () => {
    const headers = buildStorageUploadHeaders(
      {
        authorization: "Bearer signed-token",
        "x-upsert": "false",
        "Content-Type": "image/jpeg"
      },
      "image/jpeg"
    );

    expect(headers.get("authorization")).toBe("Bearer signed-token");
    expect(headers.get("x-upsert")).toBe("false");
    expect(headers.get("content-type")).toBe("image/jpeg");
  });

  it("adds a fallback mime type when the intent omits content-type", () => {
    const headers = buildStorageUploadHeaders(
      {
        authorization: "Bearer signed-token"
      },
      "application/x.scratch.sb3"
    );

    expect(headers.get("authorization")).toBe("Bearer signed-token");
    expect(headers.get("content-type")).toBe("application/x.scratch.sb3");
  });
});
