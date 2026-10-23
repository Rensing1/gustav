import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps the player and restores focus and background without native dialog APIs", async () => {
    // JSDOM deliberately supplies the same missing APIs as the legacy profile.
    for (const method of ["show", "showModal", "close"] as const) {
      expect(HTMLDialogElement.prototype[method]).toBeUndefined();
    }
    expect("inert" in HTMLElement.prototype).toBe(false);
    const background = document.createElement("button");
    background.textContent = "Outside";
    background.setAttribute("aria-hidden", "false");
    background.style.pointerEvents = "auto";
    document.body.append(background);
    const previousOverflow = document.body.style.overflow;
    const view = render(H5PTaskPlayer, { courseId: "course-1", taskId: "task-a", contentId: "content-a" });
    try {
      await waitFor(() => expect(document.querySelector("h5p-player")).toBeInTheDocument());
      const player = document.querySelector("h5p-player");
      const opener = screen.getByRole("button", { name: "Vollbild" });
      for (const closeWith of ["Escape", "button"] as const) {
        opener.focus();
        await fireEvent.click(opener);
        const dialog = screen.getByRole("dialog", { name: "H5P-Aufgabe" });
        await waitFor(() => expect(dialog).toHaveAttribute("aria-modal", "true"));
        expect(background).toHaveAttribute("aria-hidden", "true");
        expect(background.style.pointerEvents).toBe("none");
        expect(document.body.style.overflow).toBe("hidden");
        expect(screen.getByRole("button", { name: "Vollbild verlassen" })).toHaveFocus();
        background.focus();
        expect(screen.getByRole("button", { name: "Vollbild verlassen" })).toHaveFocus();
        if (closeWith === "Escape") await fireEvent.keyDown(window, { key: "Escape" });
        else await fireEvent.click(screen.getByRole("button", { name: "Vollbild verlassen" }));
        await waitFor(() => expect(dialog).not.toHaveAttribute("aria-modal", "true"));
        expect(opener).toHaveFocus();
        expect(document.querySelector("h5p-player")).toBe(player);
        expect(background).toHaveAttribute("aria-hidden", "false");
        expect(background.style.pointerEvents).toBe("auto");
        expect(document.body.style.overflow).toBe(previousOverflow);
      }
      await fireEvent.click(opener);
      view.unmount();
      expect(background).toHaveAttribute("aria-hidden", "false");
      expect(document.body.style.overflow).toBe(previousOverflow);
    } finally {
      view.unmount();
      background.remove();
    }
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
    expect(document.querySelector("h5p-player")).toBeVisible();
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
      expect(onProgressPersisted).toHaveBeenCalledWith({
        kind: "learning",
        submission: expect.objectContaining({ id: "submission-1" })
      });
    });
  });

  it("persists only the first completion event in one practice presentation", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      attempt_id: "attempt-1",
      status: "completed"
    }), { status: 201, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const onProgressPersisted = vi.fn();

    render(H5PTaskPlayer, {
      props: {
        courseId: "course-1",
        taskId: "task-a",
        contentId: "content-a",
        practiceContext: {
          sessionId: "session-1",
          itemId: "item-1",
          completionToken: "token-1",
          contextId: "context-1"
        },
        onProgressPersisted
      }
    });
    await tick();
    await Promise.resolve();
    const player = document.querySelector("h5p-player");

    for (const id of ["statement-1", "statement-2"]) {
      player?.dispatchEvent(new CustomEvent("xAPI", { detail: { statement: {
        id,
        verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
        result: { completion: true, score: { raw: 1, max: 1 } }
      } } }));
    }

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(onProgressPersisted).toHaveBeenCalledWith({
        kind: "practice",
        attemptId: "attempt-1",
        status: "completed"
      });
    });
  });

  it("keeps the player visible and does not offer progress after a failed save", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ detail: "Speichern fehlgeschlagen" }),
      { status: 503, headers: { "content-type": "application/json" } }
    )));
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

    document.querySelector("h5p-player")?.dispatchEvent(new CustomEvent("xAPI", { detail: { statement: {
      id: "statement-failed",
      verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
      result: { completion: true, score: { raw: 0, max: 1 } }
    } } }));

    expect(await screen.findByText("Speichern fehlgeschlagen")).toBeVisible();
    expect(document.querySelector("h5p-player")).toBeInTheDocument();
    expect(onProgressPersisted).not.toHaveBeenCalled();
  });
});
