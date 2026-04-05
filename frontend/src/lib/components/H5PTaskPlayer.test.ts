import { render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { describe, expect, it, vi } from "vitest";

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
});
