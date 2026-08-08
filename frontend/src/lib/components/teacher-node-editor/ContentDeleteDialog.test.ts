import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import ContentDeleteDialog from "./ContentDeleteDialog.svelte";

describe("ContentDeleteDialog", () => {
  it("names the selected content and submits explicit confirmation", () => {
    render(ContentDeleteDialog, {
      props: {
        kind: "task",
        id: "task-1",
        title: "Argumentiere begründet",
        sectionId: "section-1",
        onCancel: vi.fn()
      }
    });

    expect(screen.getByRole("dialog", { name: "Aufgabe löschen" })).toHaveTextContent("Argumentiere begründet");
    expect(document.querySelector('input[name="confirmed"]')).toHaveValue("1");
    expect(screen.getByRole("button", { name: "Aufgabe löschen" })).toBeInTheDocument();
  });

  it("cancels with Escape and a backdrop click", async () => {
    const onCancel = vi.fn();
    render(ContentDeleteDialog, {
      props: {
        kind: "material",
        id: "material-1",
        title: "Merkblatt",
        sectionId: "section-1",
        onCancel
      }
    });

    await fireEvent.keyDown(window, { key: "Escape" });
    await fireEvent.click(screen.getByRole("button", { name: "Löschdialog schließen" }));
    expect(onCancel).toHaveBeenCalledTimes(2);
  });
});
