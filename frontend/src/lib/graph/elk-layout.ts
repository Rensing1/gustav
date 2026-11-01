import type { ElkLayout } from "./module-graph-layout";

let elkPromise: Promise<{ layout: ElkLayout }> | undefined;

/** Share the existing lazy worker; a failed import remains retryable. */
export async function getElk(): Promise<{ layout: ElkLayout }> {
  if (!elkPromise) {
    elkPromise = Promise.all([
      import("elkjs/lib/elk-api.js"), import("elkjs/lib/elk-worker.min.js?url")
    ]).then(([module, worker]) => new module.default({ workerUrl: worker.default }))
      .catch((error: unknown) => { elkPromise = undefined; throw error; });
  }
  return elkPromise;
}
