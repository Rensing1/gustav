import { fireEvent, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it, vi } from "vitest";

import WorkspaceDrawer from "./WorkspaceDrawer.svelte";

const content = createRawSnippet(() => ({
  render: () => '<button type="button">Innerhalb arbeiten</button>'
}));

describe("WorkspaceDrawer", () => {
  it("closes with Escape but ignores other keys", async () => {
    const onClose = vi.fn();
    render(WorkspaceDrawer, {
      props: {
        labelledBy: "drawer-title",
        onClose,
        children: content
      }
    });

    await fireEvent.keyDown(window, { key: "Enter" });
    expect(onClose).not.toHaveBeenCalled();

    await fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes from the outside surface but not from its content", async () => {
    const onClose = vi.fn();
    render(WorkspaceDrawer, {
      props: {
        labelledBy: "drawer-title",
        onClose,
        children: content
      }
    });

    await fireEvent.click(screen.getByRole("button", { name: "Seitenleiste schließen" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    await fireEvent.click(screen.getByRole("button", { name: "Innerhalb arbeiten" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
