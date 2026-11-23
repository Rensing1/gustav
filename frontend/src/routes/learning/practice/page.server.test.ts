import { describe, expect, it, vi } from "vitest";

import { load } from "./+page.server";
import type { LearningPracticeSession } from "$lib/types/practice";

const { read, list } = vi.hoisted(() => ({ read: vi.fn(), list: vi.fn() }));
vi.mock("$lib/server/api", () => ({ readTypedJsonOrNull: read, requireBackendJson: list }));
vi.mock("$lib/server/guards", () => ({
  currentPath: (url: URL) => url.pathname + url.search,
  requireParentSpaceBootstrap: vi.fn()
}));

const a = { course_id: "course", practice_module_id: "a" };
const b = { course_id: "course", practice_module_id: "b" };
const stack = (selection: typeof a) => ({
  ...selection, course_title: "Kurs", unit_id: "unit", unit_title: "Einheit",
  module_title: selection.practice_module_id, task_count: 1, due_tasks_count: 1
});

async function loadPractice(query: string, selections: typeof a[], available = [a, b]) {
  const session = {
    id: "session", status: "active", stacks: selections,
    current_item: { ...b, latest_attempt_id: "attempt" }
  } as LearningPracticeSession;
  read.mockReset().mockResolvedValueOnce(session).mockResolvedValueOnce({ id: "attempt" });
  list.mockResolvedValue({ stacks: available.map(stack) });
  const data = await load({
    url: new URL("/learning/practice" + query, "https://app.localhost")
  } as Parameters<typeof load>[0]);
  return { data, session };
}

describe("practice module entry", () => {
  const query = "?course_id=course&practice_module_id=b";

  it("keeps mixed-session tasks and feedback out of the requested module", async () => {
    const { data } = await loadPractice(query, [a, b]);
    expect(data.activeSession).toBeNull();
    expect(data.attempt).toBeNull();
    expect(read).toHaveBeenCalledTimes(1);
    expect(data.stacks).toEqual([stack(b)]);
    expect(data.replaceActiveSessionId).toBe("session");
    expect(data.actionUrls.skip).toBe("?/skip&course_id=course&practice_module_id=b");
  });

  it("resumes an exact single-stack session", async () => {
    const { data, session } = await loadPractice(query, [b]);
    expect(data.activeSession).toBe(session);
    expect(data.attempt).toEqual({ id: "attempt" });
  });

  it("keeps a mixed session available on the general entry", async () => {
    const { data, session } = await loadPractice("", [a, b]);
    expect(data.activeSession).toBe(session);
    expect(data.stacks).toEqual([stack(a), stack(b)]);
    expect(data.actionUrls.skip).toBe("?/skip");
  });

  it("hides exercises when the requested stack is unavailable", async () => {
    const { data } = await loadPractice(query, [b], [a]);
    expect(data.activeSession).toBeNull();
    expect(data.stacks).toEqual([]);
    expect(read).toHaveBeenCalledTimes(1);
  });
});
