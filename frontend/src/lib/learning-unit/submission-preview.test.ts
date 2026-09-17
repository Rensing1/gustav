import { describe, expect, it, vi } from "vitest";
import { createSubmissionPreviewLoader, submissionPreviewText } from "./submission-preview";
import type { LearningSubmission } from "$lib/types/learning";

const snapshot = (id: string, intent: "submit" | "feedback" = "submit") => ({ id, intent }) as LearningSubmission;
const response = (rows: LearningSubmission[], status = 200) => new Response(JSON.stringify(rows), { status });

describe("submission preview loading", () => {
  it("selects the final snapshot without fetching a whole history", async () => {
    const fetcher = vi.fn().mockResolvedValue(response([snapshot("final")]));
    const changed = vi.fn();
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: changed });
    await loader.load("task");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toContain("intent=submit&limit=1&offset=0");
    expect(changed).toHaveBeenLastCalledWith("task", { status: "loaded", submission: snapshot("final") });
    await loader.load("task");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("falls back only to a saved feedback draft and keeps empty results cached", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response([])).mockResolvedValueOnce(response([snapshot("draft", "feedback")]));
    const changed = vi.fn();
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: changed });
    await loader.load("task");
    expect(fetcher.mock.calls[1][0]).toContain("intent=feedback");
    expect(changed.mock.lastCall?.[1].submission.intent).toBe("feedback");
    const emptyFetch = vi.fn().mockImplementation(() => Promise.resolve(response([])));
    const empty = createSubmissionPreviewLoader({ courseId: "course", fetcher: emptyFetch, onChange: changed });
    await empty.load("task");
    await empty.load("task");
    expect(emptyFetch).toHaveBeenCalledTimes(2);
    expect(changed.mock.lastCall?.[1]).toEqual({ status: "unavailable", submission: null });
  });

  it("deduplicates requests and never exceeds four active requests", async () => {
    let active = 0;
    let maximum = 0;
    const release: (() => void)[] = [];
    const fetcher = vi.fn(() => new Promise<Response>((resolve) => {
      active++; maximum = Math.max(maximum, active);
      release.push(() => { active--; resolve(response([snapshot("final")])); });
    }));
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: vi.fn() });
    const first = loader.load("0");
    expect(loader.load("0")).toBe(first);
    const pending = [first, ...Array.from({ length: 8 }, (_, i) => loader.load(String(i + 1)))];
    while (release.length || active) {
      release.splice(0).forEach((finish) => finish());
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    await Promise.all(pending);
    expect(maximum).toBe(4);
    expect(fetcher).toHaveBeenCalledTimes(9);
  });

  it("reports local errors, permits retry, and clears forbidden data", async () => {
    const changed = vi.fn();
    const denied = vi.fn();
    const fetcher = vi.fn().mockResolvedValueOnce(response([], 500)).mockResolvedValueOnce(response([snapshot("final")])).mockResolvedValueOnce(response([], 403));
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: changed, onDenied: denied });
    await loader.load("task");
    expect(changed.mock.lastCall?.[1].status).toBe("failed");
    await loader.load("task");
    expect(changed.mock.lastCall?.[1].submission.id).toBe("final");
    await loader.invalidate("task");
    expect(changed.mock.lastCall?.[1]).toEqual({ status: "unavailable", submission: null });
    expect(denied).toHaveBeenCalledWith("task");
  });

  it("keeps the current snapshot visible during background refresh", async () => {
    let finish!: (value: Response) => void;
    const changed = vi.fn();
    const fetcher = vi.fn().mockResolvedValueOnce(response([snapshot("final")]))
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve; }));
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: changed });
    await loader.load("task");
    const refresh = loader.invalidate("task");
    expect(changed.mock.lastCall?.[1]).toEqual({ status: "loading", submission: snapshot("final") });
    finish(response([snapshot("final")]));
    await refresh;
  });

  it("uses existing authentication recovery instead of retrying a logged-out session", async () => {
    const changed = vi.fn();
    const recoverAuth = vi.fn((response: Response) => response.status === 401);
    const fetcher = vi.fn().mockResolvedValue(response([], 401));
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: changed, recoverAuth });
    await loader.load("task");
    expect(recoverAuth).toHaveBeenCalledOnce();
    expect(fetcher).toHaveBeenCalledOnce();
    expect(changed.mock.lastCall?.[1]).toEqual({ status: "unavailable", submission: null });
  });

  it("refreshes after invalidation during a pending request and ignores disposed requests", async () => {
    let finish!: (value: Response) => void;
    const changed = vi.fn();
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValue(response([snapshot("new")]));
    const loader = createSubmissionPreviewLoader({ courseId: "course", fetcher, onChange: changed });
    const pending = loader.load("task");
    void loader.invalidate("task");
    finish(response([snapshot("old")]));
    await pending;
    await vi.waitFor(() => expect(changed.mock.lastCall?.[1].submission?.id).toBe("new"));
    loader.dispose();
    const count = changed.mock.calls.length;
    await loader.load("other");
    expect(changed).toHaveBeenCalledTimes(count);
  });
});

it("builds plain readable previews from the same safe markdown grammar", () => {
  const text = submissionPreviewText("## **Eingabe**\n\n[Quelle](https://example.com) und `Code`<br>Ausgabe<script>alert(1)</script>");
  expect(text).toContain("Eingabe");
  expect(text).toContain("Quelle und Code");
  expect(text).not.toMatch(/<|\*\*|https:|alert|##/);
});
