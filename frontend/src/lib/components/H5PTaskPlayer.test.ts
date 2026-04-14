import { render, screen, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

import H5PTaskPlayer from "./H5PTaskPlayer.svelte";

const webcomponentsRuntime = vi.hoisted(() => {
  const defineElements = vi.fn();
  return {
    defineElements,
    loadH5PWebcomponentsModule: vi.fn(async () => ({
      defineElements
    }))
  };
});

vi.mock("$lib/runtime/h5p-webcomponents", () => ({
  loadH5PWebcomponentsModule: webcomponentsRuntime.loadH5PWebcomponentsModule
}));

describe("H5PTaskPlayer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a fresh player when remounted with another task", async () => {
    const first = render(H5PTaskPlayer, {
      props: {
        courseId: "course-1",
        taskId: "task-a",
        contentId: "content-a"
      }
    });
    await tick();
    await Promise.resolve();
    expect(webcomponentsRuntime.defineElements).toHaveBeenCalledWith(["h5p-player"]);
    expect(document.querySelectorAll("h5p-player")).toHaveLength(1);
    expect(document.querySelector("h5p-player")?.getAttribute("content-id")).toBe("content-a");
    expect(screen.getByText("Bereit.")).toBeInTheDocument();

    first.unmount();
    expect(document.querySelectorAll("h5p-player")).toHaveLength(0);

    render(H5PTaskPlayer, {
      props: {
        courseId: "course-1",
        taskId: "task-b",
        contentId: "content-b"
      }
    });
    await tick();
    await Promise.resolve();
    expect(document.querySelectorAll("h5p-player")).toHaveLength(1);
    expect(document.querySelector("h5p-player")?.getAttribute("content-id")).toBe("content-b");
  });

  it("notifies the workspace after a persisted scored attempt", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: "submission-1" }), {
      status: 201,
      headers: { "content-type": "application/json" }
    }));
    vi.stubGlobal("fetch", fetchMock);

    const onProgressPersisted = vi.fn();

    render(H5PTaskPlayer, {
      props: {
        courseId: "course-1",
        taskId: "task-a",
        contentId: "content-a",
        onProgressPersisted
      }
    });

    await tick();
    await Promise.resolve();

    const player = document.querySelector("h5p-player");
    expect(player).not.toBeNull();

    player?.dispatchEvent(
      new CustomEvent("xAPI", {
        detail: {
          statement: {
            id: "statement-1",
            verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
            result: {
              completion: true,
              score: { raw: 4, max: 4 }
            }
          }
        }
      })
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(onProgressPersisted).toHaveBeenCalledTimes(1);
    });
  });
});
