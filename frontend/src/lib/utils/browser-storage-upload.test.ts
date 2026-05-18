import { describe, expect, it, vi } from "vitest";

import { prepareBrowserStorageUpload, sha256Hex } from "./browser-storage-upload";

describe("sha256Hex", () => {
  it("computes a deterministic sha256 for browser uploads", async () => {
    const file = new File([new TextEncoder().encode("teacher-upload")], "material.pdf", {
      type: "application/pdf"
    });

    await expect(sha256Hex(file)).resolves.toBe("0a69c09f7c1eca87a0a6fb108e3aeb1929a2e4bb732a021612730325fd5875b2");
  });
});

describe("prepareBrowserStorageUpload", () => {
  it("requests an intent, uploads with normalized headers and returns sha256", async () => {
    const file = new File(["pdf"], "material.pdf", { type: "application/pdf" });
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            intent_id: "intent-1",
            url: "https://storage.local/upload",
            headers: {
              "Content-Type": "application/pdf",
              authorization: "Bearer test"
            }
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const result = await prepareBrowserStorageUpload({
      fetchFn,
      intentUrl: "/api/test/upload-intents",
      intentPayload: {
        filename: "material.pdf",
        mime_type: "application/pdf",
        size_bytes: file.size
      },
      file,
      fallbackMimeType: "application/pdf"
    });

    expect(fetchFn).toHaveBeenNthCalledWith(
      1,
      "/api/test/upload-intents",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" }
      })
    );
    expect(fetchFn).toHaveBeenNthCalledWith(
      2,
      "https://storage.local/upload",
      expect.objectContaining({
        method: "PUT",
        body: file
      })
    );

    const uploadHeaders = fetchFn.mock.calls[1]?.[1]?.headers;
    expect(uploadHeaders).toBeInstanceOf(Headers);
    expect((uploadHeaders as Headers).get("content-type")).toBe("application/pdf");
    expect((uploadHeaders as Headers).get("authorization")).toBe("Bearer test");

    expect(result.intent.intent_id).toBe("intent-1");
    expect(result.sha256).toHaveLength(64);
    expect(result.mimeType).toBe("application/pdf");
  });

  it("surfaces backend detail codes from the intent request", async () => {
    const file = new File(["png"], "bild.png", { type: "image/png" });
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: "bad_request", detail: "mime_not_allowed" }), {
        status: 400,
        headers: { "content-type": "application/json" }
      })
    );

    await expect(
      prepareBrowserStorageUpload({
        fetchFn,
        intentUrl: "/api/test/upload-intents",
        intentPayload: {},
        file,
        fallbackMimeType: "image/png"
      })
    ).rejects.toThrow("mime_not_allowed");
  });

  it("starts browser auth recovery for intent 401 responses without uploading the file", async () => {
    const file = new File(["png"], "bild.png", { type: "image/png" });
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 401 }));
    const onAuthRecovery = vi.fn(() => true);

    await expect(
      prepareBrowserStorageUpload({
        fetchFn,
        intentUrl: "/api/test/upload-intents",
        intentPayload: {},
        file,
        fallbackMimeType: "image/png",
        onAuthRecovery
      })
    ).rejects.toThrow("auth_recovery_started");

    expect(onAuthRecovery).toHaveBeenCalledWith(expect.objectContaining({ status: 401 }));
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
});
