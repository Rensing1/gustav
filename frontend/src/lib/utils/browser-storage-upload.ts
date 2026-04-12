import { buildStorageUploadHeaders } from "./storage-upload-headers";

export type StorageUploadIntent = {
  intent_id: string;
  url: string;
  headers?: Record<string, string>;
  storage_key?: string;
};

export async function sha256Hex(file: Blob): Promise<string> {
  const buffer = await new Response(file).arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

export async function prepareBrowserStorageUpload(options: {
  fetchFn?: typeof fetch;
  intentUrl: string;
  intentPayload: Record<string, unknown>;
  file: File;
  fallbackMimeType: string;
}): Promise<{ intent: StorageUploadIntent; sha256: string; mimeType: string }> {
  const fetchFn = options.fetchFn ?? fetch;
  const response = await fetchFn(options.intentUrl, {
    method: "POST",
    credentials: "include",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(options.intentPayload)
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string; error?: string };
    throw new Error(payload.detail || payload.error || `intent_failed_${response.status}`);
  }

  const intent = (await response.json()) as StorageUploadIntent;
  const mimeType = options.fallbackMimeType.trim().toLowerCase() || "application/octet-stream";

  const uploadResponse = await fetchFn(intent.url, {
    method: "PUT",
    headers: buildStorageUploadHeaders(intent.headers, mimeType),
    body: options.file
  });

  if (!uploadResponse.ok) {
    throw new Error("upload_failed");
  }

  return {
    intent,
    sha256: await sha256Hex(options.file),
    mimeType
  };
}
