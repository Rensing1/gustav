import { render } from "@testing-library/svelte";
import { tick } from "svelte";
import { describe, expect, it, vi } from "vitest";

import TeacherH5PTaskEditor from "./TeacherH5PTaskEditor.svelte";

const editorRuntime = vi.hoisted(() => {
  const mountCalls: string[] = [];
  const destroyCalls: string[] = [];
  const loadH5PTaskEditorModule = vi.fn(async () => ({
    mountH5PTaskEditor(root: HTMLElement) {
      const taskId = root.dataset.taskId || "unknown";
      mountCalls.push(taskId);
      return {
        whenReady: Promise.resolve(),
        destroy: vi.fn(() => {
          destroyCalls.push(taskId);
        })
      };
    }
  }));

  return { mountCalls, destroyCalls, loadH5PTaskEditorModule };
});

vi.mock("$lib/runtime/h5p-task-editor", () => ({
  loadH5PTaskEditorModule: editorRuntime.loadH5PTaskEditorModule
}));

describe("TeacherH5PTaskEditor", () => {
  it("mounts a fresh editor instance whenever the component is remounted for another task", async () => {
    const first = render(TeacherH5PTaskEditor, {
      props: {
        unitId: "unit-1",
        sectionId: "section-1",
        taskId: "task-a",
        contentId: "content-a"
      }
    });
    await tick();
    await Promise.resolve();
    expect(editorRuntime.mountCalls).toEqual(["task-a"]);

    first.unmount();
    expect(editorRuntime.destroyCalls).toEqual(["task-a"]);

    const second = render(TeacherH5PTaskEditor, {
      props: {
        unitId: "unit-1",
        sectionId: "section-1",
        taskId: "task-b",
        contentId: "content-b"
      }
    });
    await tick();
    await Promise.resolve();
    expect(editorRuntime.mountCalls).toEqual(["task-a", "task-b"]);

    second.unmount();
    expect(editorRuntime.destroyCalls).toEqual(["task-a", "task-b"]);

    render(TeacherH5PTaskEditor, {
      props: {
        unitId: "unit-1",
        sectionId: "section-1",
        taskId: "task-a",
        contentId: "content-a"
      }
    });
    await tick();
    await Promise.resolve();
    expect(editorRuntime.mountCalls).toEqual(["task-a", "task-b", "task-a"]);
  });
});
