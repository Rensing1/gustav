import { cleanup, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LearningTaskCard from "./LearningTaskCard.svelte";
import type { LearningTask } from "$lib/types/learning";

// Exercise the real player's mount lifecycle instead of the global UI stub.
vi.mock("$lib/components/H5PTaskPlayer.svelte", async () => import("../H5PTaskPlayer.svelte"));
vi.mock("$lib/runtime/h5p-webcomponents", () => ({
  loadH5PWebcomponentsModule: async () => ({ defineElements: vi.fn() })
}));

type Player = HTMLElement & { loadContentCallback: (contentId: string) => Promise<unknown> };
function task(id: string, contentId: string): LearningTask {
  return { id, kind: "h5p", instruction_md: "Wähle die richtige Antwort.", criteria: [],
    h5p: { content_id: contentId }, h5p_completed: null, score_raw: null, score_max: null };
}
function props() {
  return { courseId: "course-a", task: task("task-a", "content-a"), unitType: "modular" as const,
    submissionFocused: true, workspaceOnly: true, onProgressPersisted: vi.fn() };
}
function complete(player: Element, id = "statement-1") {
  player.dispatchEvent(new CustomEvent("xAPI", { detail: { statement: {
    id, verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
    result: { completion: true, score: { raw: 1, max: 1 } }
  } } }));
}
async function currentPlayer(): Promise<Player> {
  await waitFor(() => expect(document.querySelectorAll("h5p-player")).toHaveLength(1));
  return document.querySelector("h5p-player") as Player;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("H5P task navigation", () => {
  it.each([
    { courseId: "course-a", taskId: "task-b", contentId: "content-b" },
    { courseId: "course-a", taskId: "task-b", contentId: "content-a" },
    { courseId: "course-b", taskId: "task-a", contentId: "content-a" },
    { courseId: "course-a", taskId: "task-a", contentId: "content-b" }
  ])("loads the selected content and scopes requests to $courseId/$taskId/$contentId", async (next) => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ id: "submission-1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const initial = props();
    const view = render(LearningTaskCard, initial);
    const first = await currentPlayer();
    complete(first);
    await waitFor(() => expect(initial.onProgressPersisted).toHaveBeenCalledTimes(1));
    fetchMock.mockClear();

    await view.rerender({ ...initial, courseId: next.courseId, task: task(next.taskId, next.contentId) });
    const second = await currentPlayer();
    expect(second).not.toBe(first);
    expect(first.isConnected).toBe(false);
    expect(second.getAttribute("content-id")).toBe(next.contentId);
    expect(second.getAttribute("context-id")).toBe(next.taskId);
    await second.loadContentCallback(next.contentId);
    const url = new URL(String(fetchMock.mock.calls[0][0]));
    expect(url.searchParams.get("course_id")).toBe(next.courseId);
    expect(url.searchParams.get("task_id")).toBe(next.taskId);
    expect(url.searchParams.get("content_id")).toBe(next.contentId);
    expect(url.searchParams.get("context_id")).toBe(next.taskId);
    fetchMock.mockClear();
    complete(first, "stale-statement");
    expect(fetchMock).not.toHaveBeenCalled();
    complete(second);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][0]).toBe(`/bff/h5p/submissions?course_id=${next.courseId}&task_id=${next.taskId}`);
  });

  it("keeps the active player when only progress is refreshed", async () => {
    const initial = props();
    const view = render(LearningTaskCard, initial);
    const first = await currentPlayer();
    await view.rerender({ ...initial, task: { ...initial.task, h5p_completed: true, score_raw: 1, score_max: 1 } });
    expect(await currentPlayer()).toBe(first);
  });

  it("does not report a late save from the previous task to the selected task", async () => {
    let resolveSave!: (response: Response) => void;
    const fetchMock = vi.fn<typeof fetch>(() => new Promise<Response>((resolve) => { resolveSave = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    const initial = props();
    const view = render(LearningTaskCard, initial);
    complete(await currentPlayer());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const onProgressPersisted = vi.fn();
    await view.rerender({ ...initial, task: task("task-b", "content-b"), onProgressPersisted });
    resolveSave(new Response(JSON.stringify({ id: "submission-a" }), { status: 201 }));
    // Wait for the response to pass through both asynchronous parsing steps.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onProgressPersisted).not.toHaveBeenCalled();
    expect((await currentPlayer()).getAttribute("content-id")).toBe("content-b");
  });
});
