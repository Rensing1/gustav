import { afterEach, expect, it, vi } from "vitest";
import { createTaskDraftPersistence } from "./task-draft-persistence";

const scope = { learnerSub: "learner", courseId: "course", taskId: "task", mode: "text" as const };
const key = "gustav.learning.submission-draft:learner:course:task:text";
const running: ReturnType<typeof createTaskDraftPersistence>[] = [];
function setup(request = vi.fn(async (_url: string, init?: RequestInit) => init?.method === "PUT"
  ? Response.json({ ...JSON.parse(init.body as string), updated_at: "2026-11-01T10:00:00Z" })
  : new Response(null, { status: 204 })), storage: Storage = sessionStorage) {
  const notify = vi.fn();
  const controller = createTaskDraftPersistence(scope, notify, { request: request as typeof fetch, storage });
  running.push(controller);
  return { controller, request, notify };
}
afterEach(() => { running.splice(0).forEach(c => c.destroy()); sessionStorage.clear(); vi.useRealTimers(); vi.restoreAllMocks(); });

it("restores server text including empty text and never saves an untouched baseline", async () => {
  const { controller, request } = setup(vi.fn(async () => Response.json({ text_body: "", updated_at: "now" })));
  await controller.load("reviewed");
  expect(controller.state.text).toBe("");
  expect(await controller.save()).toBe(true);
  expect(request).toHaveBeenCalledTimes(1);
});

it("adopts old scoped tab text, preserves whitespace and removes it only after confirmation", async () => {
  sessionStorage.setItem(key, "  Grüße\n");
  const { controller, request } = setup();
  await controller.load("reviewed");
  expect(controller.state.text).toBe("  Grüße\n");
  expect(sessionStorage.getItem(key)).toBe("  Grüße\n");
  await controller.save();
  expect(controller.state.status).toBe("saved");
  expect(sessionStorage.getItem(key)).toBeNull();
  for (const [, init] of request.mock.calls) {
    expect(new Headers(init?.headers).get("X-Draft-Owner")).toBe("learner");
  }
});

it("debounces edits and saves continuous typing within five seconds", async () => {
  vi.useFakeTimers();
  const { controller, request } = setup();
  await controller.load("");
  for (let i = 0; i < 10; i++) {
    controller.edit(String(i));
    await vi.advanceTimersByTimeAsync(500);
  }
  expect(request).toHaveBeenCalledTimes(2);
  expect(controller.state.status).toBe("saved");
});

it("keeps edits made during a request and sends them after the first response", async () => {
  let release!: (response: Response) => void;
  const request = vi.fn(async (_url: string, init?: RequestInit): Promise<Response> => {
    if (!init?.method) return new Response(null, { status: 204 });
    if (JSON.parse(init.body as string).text_body === "first") return new Promise(resolve => { release = resolve; });
    return Response.json({ text_body: "second", updated_at: "now" });
  });
  const { controller } = setup(request);
  await controller.load(""); controller.edit("first");
  const saving = controller.save();
  await vi.waitFor(() => expect(release).toBeDefined());
  controller.edit("second");
  release(Response.json({ text_body: "first", updated_at: "now" }));
  await saving;
  expect(controller.state.text).toBe("second");
  expect(controller.state.status).toBe("saved");
  expect(request).toHaveBeenCalledTimes(3);
});

it("keeps local text on failure, retries transient failures and stops on forbidden", async () => {
  vi.useFakeTimers();
  let status = 503;
  const { controller, request } = setup(vi.fn(async (_url, init) => !init?.method
    ? new Response(null, { status: 204 }) : new Response(null, { status })));
  await controller.load(""); controller.edit("offline");
  expect(await controller.save()).toBe(false);
  expect(sessionStorage.getItem(key)).toBe("offline");
  status = 403;
  await vi.advanceTimersByTimeAsync(10_000);
  expect(controller.state.status).toBe("blocked");
  const calls = request.mock.calls.length;
  await vi.advanceTimersByTimeAsync(30_000);
  window.dispatchEvent(new Event("online"));
  expect(request).toHaveBeenCalledTimes(calls);
});

it("does not unlock or write after a failed initial read", async () => {
  const { controller, request } = setup(vi.fn(async () => new Response(null, { status: 503 })));
  await controller.load("reviewed");
  controller.edit("accidental");
  expect(controller.state.ready).toBe(false);
  expect(await controller.save()).toBe(false);
  expect(request.mock.calls.every(call => !call[1]?.method)).toBe(true);
});

it("saves with unavailable browser storage and warns when both stores fail", async () => {
  const storage = { getItem() { throw Error(); }, setItem() { throw Error(); }, removeItem() { throw Error(); } } as unknown as Storage;
  const { controller, request } = setup(undefined, storage);
  await controller.load(""); controller.edit("text");
  expect(await controller.save()).toBe(true);
  request.mockImplementation(async () => { throw Error(); });
  controller.edit("new"); await controller.save();
  expect(controller.state.message).toContain("geöffnet");
});

it("ignores a late load after destruction", async () => {
  let release!: (response: Response) => void;
  const { controller, notify } = setup(vi.fn(() => new Promise<Response>(resolve => { release = resolve; })));
  const loading = controller.load("");
  await vi.waitFor(() => expect(release).toBeDefined());
  controller.destroy(); const calls = notify.mock.calls.length;
  release(Response.json({ text_body: "old task", updated_at: "now" }));
  await loading;
  expect(notify).toHaveBeenCalledTimes(calls);
});

it("serializes component replacement and restores the newer recovery text", async () => {
  let release!: (response: Response) => void;
  const first = setup(vi.fn(async (_url, init) => !init?.method ? new Response(null, { status: 204 })
    : new Promise<Response>(resolve => { release = resolve; })));
  await first.controller.load(""); first.controller.edit("old");
  const saving = first.controller.save();
  await vi.waitFor(() => expect(release).toBeDefined());
  first.controller.edit("new after send"); first.controller.destroy();
  const second = setup();
  const loading = second.controller.load("");
  expect(second.request).not.toHaveBeenCalled();
  release(Response.json({ text_body: "old", updated_at: "now" }));
  await saving; await loading;
  expect(second.controller.state.text).toBe("new after send");
  expect(await second.controller.save()).toBe(true);
});

it("warns on tab close while dirty, but not after server confirmation", async () => {
  const { controller } = setup();
  await controller.load(""); controller.edit("unsaved");
  const leaving = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(leaving);
  expect(leaving.defaultPrevented).toBe(true);
  await controller.save();
  const saved = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(saved);
  expect(saved.defaultPrevented).toBe(false);
});

it("retains recovery text and the close warning even if the initial server read fails", async () => {
  sessionStorage.setItem(key, "offline from yesterday's tab");
  const { controller } = setup(vi.fn(async () => new Response(null, { status: 503 })));
  await controller.load("");
  expect(controller.state.dirty).toBe(true);
  expect(controller.state.text).toBe("offline from yesterday's tab");
});

it("bounds a stalled save so pausing reports a recoverable failure", async () => {
  vi.useFakeTimers();
  const request = vi.fn(async (_url: string, init?: RequestInit): Promise<Response> => {
    if (!init?.method) return new Response(null, { status: 204 });
    return new Promise((_resolve, reject) => init.signal?.addEventListener("abort", () => reject(new Error("timeout"))));
  });
  const { controller } = setup(request);
  await controller.load(""); controller.edit("keep me");
  const saving = controller.save();
  await vi.advanceTimersByTimeAsync(15_000);
  expect(controller.state.status).toBe("error");
  expect(await saving).toBe(false);
  expect(sessionStorage.getItem(key)).toBe("keep me");
});
