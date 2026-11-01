import { removeLegacySubmissionDraft, submissionDraftStorageKey, type SubmissionDraftScope } from "./submission-drafts";

export type DraftState = {
  text: string;
  ready: boolean;
  dirty: boolean;
  hasDraft: boolean;
  status: "loading" | "idle" | "pending" | "saving" | "saved" | "error" | "blocked";
  message: string;
};
type Controller = ReturnType<typeof createTaskDraftPersistence>;
// Browser controllers register only when an editor mounts, never during SSR.
const active = new Set<Controller>();
const writes = new Map<string, Promise<unknown>>();

/** Run one request at a time even if a task's component is replaced mid-save. */
async function serialized<T>(key: string, action: () => Promise<T>): Promise<T> {
  const previous = writes.get(key);
  const next = (previous ?? Promise.resolve()).catch(() => {}).then(action);
  writes.set(key, next);
  try { return await next; }
  finally { if (writes.get(key) === next) writes.delete(key); }
}

export function hasPendingTaskDrafts(): boolean {
  return [...active].some(controller => controller.state.dirty);
}

/** The user explicitly chose to leave with unsaved tab-local recovery text. */
export function allowTaskDraftExit(): void {
  active.forEach(controller => controller.allowExit());
}

/** Navigation waits for confirmation; callers decide whether an explicit exit is allowed. */
export async function saveActiveTaskDrafts(): Promise<boolean> {
  const results = await Promise.all([...active].filter(controller => controller.state.dirty).map(controller => controller.save()));
  return results.every(Boolean);
}

/** Own the lifecycle of one authenticated learner's active native text editor.
 * Local storage contains only unconfirmed text. Acknowledgements clear exactly
 * their own snapshot, never later edits. The server independently authorizes
 * every request. Only real edits create drafts; fallback feedback is read-only.
 */
export function createTaskDraftPersistence(
  scope: SubmissionDraftScope,
  notify: (state: DraftState) => void,
  options: { request?: typeof fetch; storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> } = {}
) {
  const key = submissionDraftStorageKey(scope);
  if (!key) throw new Error("Authenticated learner required");
  const storageKey: string = key;
  const url = `/api/learning/courses/${encodeURIComponent(scope.courseId)}/tasks/${encodeURIComponent(scope.taskId)}/draft`;
  const request = options.request ?? fetch;
  let storage: typeof options.storage;
  try { storage = options.storage ?? window.sessionStorage; } catch { /* Server saving still works. */ }
  let state: DraftState = { text: "", ready: false, dirty: false, hasDraft: false, status: "loading", message: "Entwurf wird geladen …" };
  let alive = true;
  let baseline = "";
  let exitAllowed = false;
  let confirmed: string | undefined;
  let saving: Promise<boolean> | null = null;
  let loading: Promise<void> | null = null;
  let localTimer: ReturnType<typeof setTimeout> | undefined;
  let debounce: ReturnType<typeof setTimeout> | undefined;
  let deadline: ReturnType<typeof setTimeout> | undefined;
  let retry: ReturnType<typeof setTimeout> | undefined;

  async function requestDraft(init: RequestInit): Promise<Response> {
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), 15_000);
    const headers = new Headers(init.headers);
    headers.set("X-Draft-Owner", encodeURIComponent(scope.learnerSub!));
    try { return await request(url, { ...init, headers, signal: abort.signal }); }
    finally { clearTimeout(timeout); }
  }

  function publish(patch: Partial<DraftState>) {
    state = { ...state, ...patch };
    if (alive) notify(state);
  }
  function checkpoint() {
    clearTimeout(localTimer); localTimer = undefined;
    if (!state.dirty) return;
    try { storage?.setItem(storageKey, state.text); } catch { /* Keep memory and report server failure visibly. */ }
  }
  function clearTimers() {
    clearTimeout(debounce); clearTimeout(deadline); clearTimeout(retry);
    debounce = deadline = retry = undefined;
  }
  function schedule() {
    if (!alive || state.status === "blocked") return;
    clearTimeout(debounce);
    debounce = setTimeout(() => void save(), 1000);
    deadline ??= setTimeout(() => void save(), 5000);
  }
  function failed(status = 0) {
    const blocked = [401, 403, 404, 400, 422].includes(status);
    const message = status === 401
      ? "Noch nicht gespeichert. Bitte melde dich erneut an und lasse diesen Tab geöffnet."
      : [403, 404].includes(status)
        ? "Noch nicht gespeichert. Der Zugriff auf diese Aufgabe ist nicht mehr möglich. Bitte lasse diesen Tab geöffnet."
        : [400, 422].includes(status)
          ? "Noch nicht gespeichert. Bitte prüfe den Text; erlaubt sind höchstens 65.536 Zeichen."
          : "Noch nicht auf dem Server gespeichert. Bitte lasse diese Seite geöffnet. Wir versuchen es erneut.";
    clearTimers();
    publish({ status: blocked ? "blocked" : "error", message });
    if (!blocked && alive) retry = setTimeout(() => void (state.ready ? save() : load(baseline)), 10_000);
  }
  async function load(fallback: string): Promise<void> {
    if (!alive) return;
    if (loading) return loading;
    baseline = fallback;
    if (!state.dirty) {
      try {
        const local = storage?.getItem(storageKey);
        if (local !== null && local !== undefined) publish({ text: local, dirty: true, hasDraft: true });
      } catch { /* A server draft can still be recovered without local storage. */ }
    }
    clearTimers();
    publish({ status: "loading", ready: false, message: "Entwurf wird geladen …" });
    loading = (async () => {
      try {
        // An older instance may still be writing this task when it is reopened.
        await writes.get(storageKey)?.catch(() => {});
        if (!alive) return;
        const response = await requestDraft({ credentials: "same-origin", cache: "no-store" });
        if (!alive) return;
        if (response.status !== 200 && response.status !== 204) { failed(response.status); return; }
        const server = response.status === 204 ? null : await response.json() as { text_body: string };
        if (server && typeof server.text_body !== "string") throw Error("Invalid draft response");
        if (!alive) return;
        let local: string | null = state.dirty ? state.text : null;
        try {
          local ??= storage?.getItem(storageKey) ?? null;
          removeLegacySubmissionDraft(scope);
        } catch { /* A missing recovery store must not block a healthy server. */ }
        confirmed = server?.text_body;
        const text = local ?? server?.text_body ?? baseline;
        const dirty = local !== null && local !== confirmed;
        publish({ text, ready: true, dirty, hasDraft: local !== null || server !== null,
          status: dirty ? "pending" : server ? "saved" : "idle",
          message: dirty ? "Noch nicht gespeichert" : server ? "Entwurf gespeichert – noch nicht abgegeben" : "Dein Entwurf wird beim Schreiben automatisch gespeichert." });
        if (dirty) { checkpoint(); schedule(); }
        else if (local !== null) { try { storage?.removeItem(storageKey); } catch { /* Optional recovery store. */ } }
      } catch { if (alive) failed(); }
    })();
    try { await loading; } finally { loading = null; }
  }
  function edit(text: string) {
    if (!alive || !state.ready || state.text === text) return;
    exitAllowed = false;
    publish({ text, dirty: true, hasDraft: true,
      ...(state.status === "blocked" ? {} : { status: "pending" as const, message: "Noch nicht gespeichert" }) });
    clearTimeout(localTimer);
    localTimer = setTimeout(checkpoint, 200);
    // Validation failures can be corrected by editing; access failures cannot.
    if (state.status === "blocked" && state.message.includes("65.536")) publish({ status: "pending" });
    schedule();
  }
  async function save(): Promise<boolean> {
    if (saving) return saving;
    if (!state.ready || state.status === "blocked") return false;
    if (!state.dirty) return true;
    clearTimers(); checkpoint();
    saving = (async () => {
      while (alive && state.dirty) {
        const text = state.text;
        publish({ status: "saving", message: "Wird gespeichert …" });
        try {
          const response = await serialized(storageKey, () => requestDraft({
            method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text_body: text })
          }));
          if (response.status !== 200) { if (alive) failed(response.status); return false; }
          const result = await response.json() as { text_body: string };
          if (result.text_body !== text) throw Error("Draft confirmation mismatch");
          confirmed = text;
          // A replacement editor may already have written a different recovery draft.
          if (state.text === text) {
            try { if (storage?.getItem(storageKey) === text) storage.removeItem(storageKey); } catch { /* Best effort cleanup. */ }
            publish({ dirty: false, status: "saved", message: "Entwurf gespeichert – noch nicht abgegeben" });
          }
        } catch { if (alive) failed(); return false; }
      }
      if (alive) clearTimers();
      return !state.dirty;
    })();
    try { return await saving; } finally { saving = null; }
  }
  function setBaseline(text: string) {
    baseline = text;
    if (state.ready && !state.hasDraft && !state.dirty) publish({ text });
  }
  function online() { if (state.status !== "blocked") void (state.ready ? save() : load(baseline)); }
  function beforeUnload(event: BeforeUnloadEvent) {
    if (!state.dirty || exitAllowed) return;
    checkpoint(); event.preventDefault(); event.returnValue = "";
  }
  function destroy() {
    if (!alive) return;
    checkpoint(); alive = false; clearTimers(); active.delete(controller);
    window.removeEventListener("online", online);
    window.removeEventListener("pagehide", checkpoint);
    window.removeEventListener("beforeunload", beforeUnload);
  }
  const controller = { get state() { return state; }, load, edit, save, setBaseline, checkpoint, destroy, allowExit: () => { exitAllowed = true; } };
  active.add(controller);
  window.addEventListener("online", online);
  window.addEventListener("pagehide", checkpoint);
  window.addEventListener("beforeunload", beforeUnload);
  return controller;
}
