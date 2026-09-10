type Viewport = { x: number; y: number; zoom: number };
type CameraStorage = Pick<Storage, "getItem" | "setItem">;

/** Restore a tab-local camera, never accepting malformed or out-of-range data. */
export function readViewport(storage: CameraStorage, key: string): Viewport | null {
  try {
    const value = JSON.parse(storage.getItem(key) ?? "null");
    if (value && [value.x, value.y, value.zoom].every((n) => typeof n === "number" && Number.isFinite(n))
      && value.zoom >= 0.1 && value.zoom <= 1.26) {
      return { x: value.x, y: value.y, zoom: value.zoom };
    }
  } catch { /* Storage is optional, including in restricted browsing modes. */ }
  return null;
}

/** Remember only presentation coordinates, with no account or content data. */
export function writeViewport(storage: CameraStorage, key: string, viewport: Viewport): void {
  try {
    storage.setItem(key, JSON.stringify(viewport));
  } catch { /* A denied storage write must not interrupt editing or navigation. */ }
}
