import path from "node:path";
import { access, mkdir } from "node:fs/promises";
import { constants as fsConstants } from "node:fs";


export function buildStorageDirs(storageRoot) {
  return {
    root: storageRoot,
    libraries: path.join(storageRoot, "libraries"),
    content: path.join(storageRoot, "content"),
    tmp: path.join(storageRoot, "tmp"),
    userdata: path.join(storageRoot, "userdata"),
    uploads: path.join(storageRoot, "uploads"),
  };
}


export async function probeStorageDirs(storageDirs, deps = {}) {
  const mkdirFn = deps.mkdir || mkdir;
  const accessFn = deps.access || access;
  const writeFlag = deps.writeFlag ?? fsConstants.W_OK;

  try {
    await mkdirFn(storageDirs.libraries, { recursive: true });
    await mkdirFn(storageDirs.content, { recursive: true });
    await mkdirFn(storageDirs.tmp, { recursive: true });
    await mkdirFn(storageDirs.userdata, { recursive: true });
    await mkdirFn(storageDirs.uploads, { recursive: true });
    await accessFn(storageDirs.tmp, writeFlag);
    return { ok: true, root: storageDirs.root };
  } catch (err) {
    return { ok: false, root: storageDirs.root, error: String(err) };
  }
}


export function sanitizeHeaderFilename(value) {
  // Content-Disposition is a response header and must never contain control
  // characters (CR/LF). Keep a conservative ASCII token to avoid header errors.
  const raw = String(value || "").trim();
  const safe = raw.replace(/[^a-zA-Z0-9._-]/g, "_").replace(/_+/g, "_").slice(0, 80);
  return safe || "download";
}
