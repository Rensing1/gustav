/** Confirm runtime saves before discarding a user's tab-local recovery draft.
 * Learning scores use a separate API. This adapter stores no credentials or URLs
 * in the tab; identity and the write target come from the authorized player model.
 */
export type H5PStateModel = { integration: {
  user?: { id?: string }; saveFreq?: number | boolean;
  ajax?: { contentUserData?: string };
} };
export type H5PStateInstance = { getCurrentState?: () => unknown };
export type H5PStateJQuery = {
  ajaxTransport: (type: string, factory: (options: { type: string; url: string; async?: boolean; data?: string }) => {
    send: (headers: object, complete: (...args: unknown[]) => void) => void; abort: () => void;
  } | undefined) => void;
};
type CoreWriter = { checkpoint: () => void; save: () => Promise<void> };
const coreWriters = new WeakMap<H5PStateJQuery, Map<string, CoreWriter | null>>();

/** Register once per H5P runtime; closed registry entries retain no state or DOM references. */
function routeCoreSaves(jquery: H5PStateJQuery, target: string, writer: CoreWriter): () => void {
  let routes = coreWriters.get(jquery);
  if (!routes) {
    const registry = new Map<string, CoreWriter | null>();
    routes = registry; coreWriters.set(jquery, registry);
    jquery.ajaxTransport("+json", (options) => {
      if (options.type !== "POST" || new URLSearchParams(options.data).get("data") === "0") return;
      let url: string;
      try { url = new URL(options.url, location.href).href; } catch { return; }
      if (!registry.has(url)) return;
      return {
        send(_headers, complete) {
          const current = registry.get(url);
          if (!current) { complete(0, "error"); return; }
          if (options.async === false) {
            current.checkpoint(); complete(0, "error"); // Tab recovery is not a server acknowledgement.
          } else {
            void current.save().then(() => complete(200, "success", { text: '{"success":true}' }, "Content-Type: application/json"),
              () => complete(0, "error"));
          }
        },
        abort() { /* The shared writer still owns the newest edit. */ }
      };
    });
  }
  routes.set(target, writer);
  return () => {
    // Stop an unmounted Core instance from overwriting its replacement.
    if (routes.get(target) === writer) routes.set(target, null);
  };
}

type Status = { tone: "progress" | "success" | "error"; title: string };
type Draft = { state: string; savedAt: number };
// Remounting a player must not let an older request overwrite its replacement.
const writes = new Map<string, Promise<void>>();
const draftLifetime = 24 * 60 * 60 * 1000;
const failure = "Bearbeitungsstand noch nicht gespeichert. Bitte bleibe auf dieser Seite und versuche es erneut.";

/** Create one writer for an authenticated, writable content/task context.
 * The server still checks every POST. Read-only/review models never replay drafts.
 */
export function createH5PStatePersistence(
  model: H5PStateModel, contentId: string, contextId: string,
  notify: (status: Status) => void, request: typeof fetch = fetch
) {
  const integration = model.integration;
  const owner = integration?.user?.id ?? "";
  const template = integration?.ajax?.contentUserData;
  if (!owner || !template || integration.saveFreq === false) return null;
  let url: URL;
  try {
    url = new URL(template.replace(":contentId", encodeURIComponent(contentId))
      .replace(":dataType", "state").replace(":subContentId", "0"), location.href);
  } catch { return null; }
  if (url.origin !== location.origin || url.pathname !== `/h5p/contentUserData/${encodeURIComponent(contentId)}/state/0`
    || url.searchParams.get("contextId") !== contextId
    || url.searchParams.has("review_mode") || url.searchParams.has("review_id")
    || url.searchParams.has("asUserId") || url.searchParams.get("ignorePost") === "yes") return null;
  const key = "gustav.learning.h5p-draft:" + JSON.stringify([owner, contentId, contextId]);
  let instance: H5PStateInstance | undefined;
  let latest: string | undefined;
  let confirmed: string | undefined;
  let pending = false;
  let captureFailed = false;
  let retryAt = 0;
  let active = true;
  let departing = false;
  let saving: Promise<void> | undefined;
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let interval: ReturnType<typeof setInterval> | undefined;
  let detach = () => {};
  let detachCore = () => {};

  function readDraft(): Draft | null {
    try {
      const value = JSON.parse(sessionStorage.getItem(key) ?? "null") as Draft | null;
      if (!value) return null;
      if (typeof value.state !== "string" || !Number.isFinite(value.savedAt)
        || value.savedAt > Date.now() || Date.now() - value.savedAt > draftLifetime) {
        sessionStorage.removeItem(key); return null;
      }
      JSON.parse(value.state);
      return value;
    } catch { return null; }
  }
  function keepDraft() {
    try { sessionStorage.setItem(key, JSON.stringify({ state: latest, savedAt: Date.now() })); return true; }
    catch { notify({ tone: "error", title: failure }); return false; }
  }
  function capture() {
    if (!instance?.getCurrentState) return;
    try {
      const state = JSON.stringify(instance.getCurrentState());
      captureFailed = false;
      if (state === undefined || state === latest) return;
      latest = state;
      pending = state !== confirmed || saving !== undefined;
      if (pending) {
        if (keepDraft()) notify({ tone: "progress", title: "Bearbeitungsstand wird gespeichert …" });
      } else if (readDraft()) sessionStorage.removeItem(key);
    } catch { captureFailed = true; notify({ tone: "error", title: failure }); }
  }
  async function persist() {
    if (saving) return saving;
    const previous = writes.get(key) ?? Promise.resolve();
    const next = previous.catch(() => {}).then(async () => {
      // One request at a time; intermediate edits collapse into the latest snapshot.
      while (pending && latest !== undefined) {
        if (departing) throw new Error(failure);
        const state = latest;
        const body = new URLSearchParams({ data: state, preload: "1", invalidate: "1" }).toString();
        if (new Blob([body]).size > 2 * 1024 * 1024) throw new Error(failure);
        controller = new AbortController();
        const response = await request(url.href, {
          method: "POST", credentials: "include", signal: controller.signal,
          headers: { "content-type": "application/x-www-form-urlencoded;charset=UTF-8", "x-h5p-state-owner": owner }, body
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || result.success !== true) throw new Error(failure);
        confirmed = state;
        // A slow acknowledgement must never remove a newer, still pending edit.
        if (readDraft()?.state === state) sessionStorage.removeItem(key);
        if (latest === state) {
          pending = false; notify({ tone: "success", title: "Bearbeitungsstand gespeichert." });
        }
      }
    });
    saving = next; writes.set(key, next);
    try { await next; }
    catch { retryAt = Date.now() + 5000; notify({ tone: "error", title: failure }); throw new Error(failure); }
    // Retain only the settled void promise until the next model read. The first
    // model request may have raced this write, even if it has just completed.
    finally { saving = undefined; controller = undefined; }
  }
  async function save() {
    capture();
    if (pending && latest !== undefined) await persist();
  }
  function schedule() {
    if (!active) return;
    departing = false;
    // Read after the content library's own event handler has updated its state.
    queueMicrotask(capture);
    clearTimeout(timer);
    timer = setTimeout(() => { void save().catch(() => {}); }, 200);
  }
  function leaving(event: Event) {
    capture();
    // Reload cannot wait for a network response. Preserve the last edit in this tab.
    if (event.type === "beforeunload" && (captureFailed || pending && readDraft()?.state !== latest)) {
      departing = false; // Staying after the warning must still allow foreground saves.
      event.preventDefault(); (event as BeforeUnloadEvent).returnValue = "";
      return;
    }
    departing = true;
    clearTimeout(timer); controller?.abort();
  }
  function resume() {
    departing = false;
    void save().catch(() => {});
  }
  return {
    async restore(): Promise<boolean> {
      // A previous mount may still have a normal request in flight in this document.
      const previous = writes.get(key);
      await previous?.catch(() => {});
      if (writes.get(key) === previous) writes.delete(key);
      const draft = readDraft();
      if (!draft) return previous !== undefined;
      latest = draft.state; pending = true;
      await persist();
      writes.delete(key);
      return true;
    },
    start(currentInstance: H5PStateInstance, root: HTMLElement, jquery?: H5PStateJQuery) {
      instance = currentInstance;
      // A generated initial state (for example randomized order) is not yet a
      // confirmed server snapshot. Restored snapshots already have confirmation.
      capture();
      // Keep Core's state-loading semantics. Its autosaves must share our writer;
      // setting saveFreq=false would also stop H5P from passing previousState.
      if (jquery) detachCore = routeCoreSaves(jquery, url.href, {
        checkpoint: () => leaving(new Event("pagehide")), save
      });
      for (const event of ["input", "change", "click", "pointerup", "xAPI"]) root.addEventListener(event, schedule);
      window.addEventListener("beforeunload", leaving);
      window.addEventListener("pagehide", leaving);
      window.addEventListener("pageshow", resume);
      // Some libraries change state without a DOM event (for example media progress).
      interval = setInterval(() => { if (!departing && Date.now() >= retryAt) void save().catch(() => {}); }, 1000);
      detach = () => {
        for (const event of ["input", "change", "click", "pointerup", "xAPI"]) root.removeEventListener(event, schedule);
        window.removeEventListener("beforeunload", leaving);
        window.removeEventListener("pagehide", leaving);
        window.removeEventListener("pageshow", resume);
      };
    },
    save,
    destroy() {
      capture();
      if (!departing && pending && latest !== undefined) void persist().catch(() => {});
      active = false; clearTimeout(timer); clearInterval(interval); detach(); detachCore(); instance = undefined;
    }
  };
}
