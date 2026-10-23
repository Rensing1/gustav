import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { H5PStateModel } from "./h5p-state-persistence";
let createH5PStatePersistence: typeof import("./h5p-state-persistence").createH5PStatePersistence;
beforeEach(async () => {
  vi.resetModules();
  ({ createH5PStatePersistence } = await import("./h5p-state-persistence"));
});

const model = (user = "learner-1") => ({ integration: {
  user: { id: user }, saveFreq: 5,
  ajax: { contentUserData: "/h5p/contentUserData/:contentId/:dataType/:subContentId?contextId=task-1" }
} } satisfies H5PStateModel);
const large = { answer: "Äußere Begründung. ".repeat(6000) };
const key = "gustav.learning.h5p-draft:" + JSON.stringify(["learner-1", "42", "task-1"]);
const ok = () => new Response('{"success":true}', { status: 200 });
const make = (fetcher = vi.fn(async () => ok()), nextModel = model()) => ({
  fetcher, persistence: createH5PStatePersistence(nextModel, "42", "task-1", vi.fn(), fetcher)!
});
afterEach(() => { sessionStorage.clear(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe("confirmed H5P state persistence", () => {
  it("confirms the initial runtime state instead of merely assuming it was stored", async () => {
    const { persistence, fetcher } = make();
    persistence.start({ getCurrentState: () => ({ randomizedOrder: [2, 1] }) }, document.createElement("div"));
    await persistence.save();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(JSON.parse(new URLSearchParams(String((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body)).get("data")!)).toEqual({ randomizedOrder: [2, 1] });
    await persistence.save(); expect(fetcher).toHaveBeenCalledTimes(1); persistence.destroy();
  });
  it("saves a state above the Beacon budget through an ordinary confirmed request", async () => {
    const { persistence, fetcher } = make(); let state = { answer: "" };
    persistence.start({ getCurrentState: () => state }, document.createElement("div")); state = large;
    await persistence.save();
    const [url, options] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/h5p/contentUserData/42/state/0?contextId=task-1");
    expect(new Blob([String(options.body)]).size).toBeGreaterThan(65536);
    expect(options.keepalive).not.toBe(true); expect(options.credentials).toBe("include");
    expect(JSON.parse(new URLSearchParams(String(options.body)).get("data")!)).toEqual(large);
    expect(sessionStorage.getItem(key)).toBeNull(); persistence.destroy();
  });
  it("keeps the newest state during reload and replays it before player initialization", async () => {
    const first = make(); let state = { answer: "" };
    first.persistence.start({ getCurrentState: () => state }, document.createElement("div")); state = large;
    window.dispatchEvent(new Event("pagehide"));
    expect(JSON.parse(sessionStorage.getItem(key)!).state).toBe(JSON.stringify(large));
    const second = make(); await expect(second.persistence.restore()).resolves.toBe(true);
    expect(second.fetcher).toHaveBeenCalledTimes(1); expect(sessionStorage.getItem(key)).toBeNull();
    first.persistence.destroy(); second.persistence.destroy();
  });
  it("does not erase an unconfirmed draft after HTTP or JSON rejection", async () => {
    for (const response of [() => new Response("{}", { status: 403 }), () => new Response('{"success":false}')]) {
      const { persistence } = make(vi.fn(async () => response())); let state = { answer: "" };
      persistence.start({ getCurrentState: () => state }, document.createElement("div")); state = large;
      await expect(persistence.save()).rejects.toThrow(); expect(sessionStorage.getItem(key)).not.toBeNull();
      persistence.destroy();
    }
  });
  it("isolates pending states by user, content and context and rejects review models", async () => {
    sessionStorage.setItem(key, JSON.stringify({ state: JSON.stringify(large), savedAt: Date.now() }));
    const fetcher = vi.fn(async () => ok());
    for (const [user, content, context] of [["other", "42", "task-1"], ["learner-1", "43", "task-1"], ["learner-1", "42", "task-2"]]) {
      const persistence = createH5PStatePersistence(model(user), content, context, vi.fn(), fetcher);
      if (persistence) await expect(persistence.restore()).resolves.toBe(false);
    }
    const review = model(); review.integration.ajax.contentUserData += "&ignorePost=yes&review_mode=true";
    expect(createH5PStatePersistence(review, "42", "task-1", vi.fn(), fetcher)).toBeNull();
    const foreign = model(); foreign.integration.ajax.contentUserData = "https://foreign.example/h5p/contentUserData/42/state/0";
    expect(createH5PStatePersistence(foreign, "42", "task-1", vi.fn(), fetcher)).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("keeps a newer draft until its own serialized request has been confirmed", async () => {
    let resolveFirst!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { resolveFirst = resolve; }))
      .mockImplementationOnce(async () => ok());
    const { persistence } = make(fetcher); let state = { answer: "" };
    persistence.start({ getCurrentState: () => state }, document.createElement("div"));
    state = { answer: "first" }; const first = persistence.save();
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    state = large; const second = persistence.save(); expect(fetcher).toHaveBeenCalledTimes(1);
    resolveFirst(ok()); await first; await second;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(JSON.parse(new URLSearchParams(fetcher.mock.calls[1][1].body).get("data")!)).toEqual(large);
    expect(sessionStorage.getItem(key)).toBeNull(); persistence.destroy();
  });
  it("routes Core autosaves through the same writer and checkpoints sync saves without XHR", async () => {
    const { persistence, fetcher } = make(); let state = { answer: "" };
    let factory!: (options: { type: string; url: string; async?: boolean }) => { send: (headers: object, complete: (...args: unknown[]) => void) => void } | undefined;
    const jquery = { ajaxTransport: vi.fn((_type: string, next: typeof factory) => { factory = next; }) };
    persistence.start({ getCurrentState: () => state }, document.createElement("div"), jquery);
    state = large;
    const complete = vi.fn();
    factory({ type: "POST", async: false, url: "/h5p/contentUserData/42/state/0?contextId=task-1" })!.send({}, complete);
    expect(fetcher).not.toHaveBeenCalled();
    expect(JSON.parse(sessionStorage.getItem(key)!).state).toBe(JSON.stringify(large));
    expect(complete).toHaveBeenCalledWith(0, "error");
    const unrelated = factory({ type: "POST", async: true, url: "/h5p/contentUserData/43/state/0?contextId=task-1" });
    expect(unrelated).toBeUndefined();
    window.dispatchEvent(new Event("pageshow"));
    const normal = vi.fn();
    factory({ type: "POST", async: true, url: "/h5p/contentUserData/42/state/0?contextId=task-1" })!.send({}, normal);
    await vi.waitFor(() => expect(normal).toHaveBeenCalled());
    expect(fetcher).toHaveBeenCalledTimes(1);
    persistence.destroy();
    const stale = vi.fn();
    factory({ type: "POST", async: true, url: "/h5p/contentUserData/42/state/0?contextId=task-1" })!.send({}, stale);
    expect(stale).toHaveBeenCalledWith(0, "error");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("removes an unsent draft when the learner reverts to the confirmed state", async () => {
    const { persistence, fetcher } = make(); let state = { answer: "original" };
    persistence.start({ getCurrentState: () => state }, document.createElement("div"));
    await persistence.save();
    state = large; window.dispatchEvent(new Event("pagehide"));
    state = { answer: "original" }; window.dispatchEvent(new Event("pagehide"));
    expect(sessionStorage.getItem(key)).toBeNull();
    await persistence.save(); expect(fetcher).toHaveBeenCalledTimes(1); persistence.destroy();
  });
  it("coalesces repeated saves while an earlier request is still pending", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }))
      .mockImplementation(async () => ok());
    const { persistence } = make(fetcher); let state = { answer: "" };
    persistence.start({ getCurrentState: () => state }, document.createElement("div")); state = large;
    const saves = [persistence.save(), persistence.save(), persistence.save()];
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    resolve(ok()); await Promise.all(saves);
    expect(fetcher).toHaveBeenCalledTimes(1); persistence.destroy();
  });
  it("never starts a normal network request after pagehide and retains recovery data", async () => {
    const { persistence, fetcher } = make(); let state = { answer: "" };
    persistence.start({ getCurrentState: () => state }, document.createElement("div")); state = large;
    window.dispatchEvent(new Event("pagehide"));
    await expect(persistence.save()).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled(); expect(sessionStorage.getItem(key)).not.toBeNull();
    persistence.destroy();
  });
  it("registers one Core transport across remounts and keeps the newest writer active", async () => {
    const callbacks: Array<(options: { type: string; url: string }) => unknown> = [];
    const jquery = { ajaxTransport: vi.fn((_type: string, next: (options: { type: string; url: string }) => unknown) => { callbacks.push(next); }) };
    const first = make(), second = make();
    first.persistence.start({ getCurrentState: () => ({ answer: "first" }) }, document.createElement("div"), jquery);
    second.persistence.start({ getCurrentState: () => ({ answer: "second" }) }, document.createElement("div"), jquery);
    first.persistence.destroy();
    expect(jquery.ajaxTransport).toHaveBeenCalledTimes(1);
    await second.persistence.save();
    second.persistence.destroy();
  });
  it("requests a fresh model after a previous mount's write, even if it just completed", async () => {
    for (const waitForCompletion of [false, true]) {
      let resolve!: (value: Response) => void;
      const fetcher = vi.fn(() => new Promise<Response>(done => { resolve = done; }));
      const first = make(fetcher); let state = { answer: "" };
      first.persistence.start({ getCurrentState: () => state }, document.createElement("div"));
      state = large; const writing = first.persistence.save();
      await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
      if (waitForCompletion) { resolve(ok()); await writing; }
      const second = make(); const refresh = second.persistence.restore();
      if (!waitForCompletion) { resolve(ok()); await writing; }
      await expect(refresh).resolves.toBe(true);
      expect(second.fetcher).not.toHaveBeenCalled();
      first.persistence.destroy(); second.persistence.destroy();
    }
  });
  it("does not replay expired or malformed recovery entries", async () => {
    for (const draft of [
      { state: JSON.stringify(large), savedAt: Date.now() - 25 * 60 * 60 * 1000 },
      { state: JSON.stringify(large), savedAt: Date.now() + 60000 },
      { state: "invalid JSON", savedAt: Date.now() }
    ]) {
      sessionStorage.setItem(key, JSON.stringify(draft));
      const { persistence, fetcher } = make();
      await expect(persistence.restore()).resolves.toBe(false);
      expect(fetcher).not.toHaveBeenCalled(); persistence.destroy();
    }
  });
  it("preserves an oversized draft without claiming success or increasing the server limit", async () => {
    const { persistence, fetcher } = make(); let state = { answer: "" };
    persistence.start({ getCurrentState: () => state }, document.createElement("div"));
    state = { answer: "x".repeat(2 * 1024 * 1024) };
    await expect(persistence.save()).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled(); expect(sessionStorage.getItem(key)).not.toBeNull();
    persistence.destroy();
  });
  it("captures input in the foreground and warns before leaving if tab storage fails", async () => {
    vi.useFakeTimers(); const { persistence, fetcher } = make(); const root = document.createElement("div");
    let state = { answer: "" }; persistence.start({ getCurrentState: () => state }, root); state = large;
    root.dispatchEvent(new Event("input")); await vi.advanceTimersByTimeAsync(300);
    expect(fetcher).toHaveBeenCalledTimes(1); state = { answer: "new" };
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("quota"); });
    const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true); persistence.destroy();
  });
});
