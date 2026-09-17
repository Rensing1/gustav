import { markdownPlainText } from "$lib/utils/markdown";
import type { LearningSubmission, SubmissionHistoryLoadState } from "$lib/types/learning";

export type SubmissionPreviewState = {
  status: SubmissionHistoryLoadState;
  submission: LearningSubmission | null;
};

export const submissionPreviewText = markdownPlainText;

/** Read one owned snapshot per task without treating it as a complete history.
 * The server owns access checks and intent filtering; this page-scoped loader
 * only limits concurrency and prevents stale responses from replacing new data.
 */
export function createSubmissionPreviewLoader({ courseId, fetcher, onChange, onDenied, recoverAuth }: {
  courseId: string;
  fetcher: typeof fetch;
  onChange: (taskId: string, state: SubmissionPreviewState) => void;
  onDenied?: (taskId: string) => void;
  recoverAuth?: (response: Response) => boolean;
}) {
  const states = new Map<string, SubmissionPreviewState>();
  const pending = new Map<string, Promise<void>>();
  const revisions = new Map<string, number>();
  const queue: Array<() => Promise<void>> = [];
  const controller = new AbortController();
  let running = 0;
  let disposed = false;

  function publish(taskId: string, state: SubmissionPreviewState) {
    if (disposed) return;
    states.set(taskId, state);
    onChange(taskId, state);
  }

  function drain() {
    while (!disposed && running < 4 && queue.length) {
      running++;
      void queue.shift()!().finally(() => { running--; drain(); });
    }
  }

  async function read(taskId: string): Promise<SubmissionPreviewState> {
    for (const intent of ["submit", "feedback"]) {
      const url = `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/submissions?intent=${intent}&limit=1&offset=0`;
      const response = await fetcher(url, { credentials: "include", cache: "no-store", signal: controller.signal });
      if (disposed) return { status: "unavailable", submission: null };
      if (recoverAuth?.(response)) return { status: "unavailable", submission: null };
      if (response.status === 403 || response.status === 404) {
        onDenied?.(taskId);
        return { status: "unavailable", submission: null };
      }
      if (!response.ok) throw new Error("preview_load_failed");
      const entries = await response.json() as LearningSubmission[];
      if (entries[0]) return { status: "loaded", submission: entries[0] };
    }
    return { status: "unavailable", submission: null };
  }

  function load(taskId: string): Promise<void> {
    if (disposed) return Promise.resolve();
    const inFlight = pending.get(taskId);
    if (inFlight) return inFlight;
    if (["loaded", "unavailable"].includes(states.get(taskId)?.status ?? "")) return Promise.resolve();
    let resolve!: () => void;
    const promise = new Promise<void>((done) => { resolve = done; });
    pending.set(taskId, promise);
    publish(taskId, { status: "loading", submission: states.get(taskId)?.submission ?? null });
    queue.push(async () => {
      try {
        // An edit may finish while an older preview is in flight. Retry inside
        // this same slot instead of publishing an obsolete snapshot.
        while (!disposed) {
          const revision = revisions.get(taskId) ?? 0;
          let state: SubmissionPreviewState;
          try { state = await read(taskId); }
          catch { state = { status: "failed", submission: null }; }
          if (revision !== (revisions.get(taskId) ?? 0)) continue;
          publish(taskId, state);
          break;
        }
      } finally {
        pending.delete(taskId);
        resolve();
      }
    });
    drain();
    return promise;
  }

  return {
    load,
    invalidate(taskId: string): Promise<void> {
      revisions.set(taskId, (revisions.get(taskId) ?? 0) + 1);
      if (!states.has(taskId)) return Promise.resolve();
      states.set(taskId, { status: "not_loaded", submission: states.get(taskId)?.submission ?? null });
      return load(taskId);
    },
    dispose() {
      disposed = true;
      controller.abort();
      // Settle queued consumers as well as aborting active network requests.
      queue.splice(0).forEach((job) => { void job(); });
      states.clear();
    }
  };
}
