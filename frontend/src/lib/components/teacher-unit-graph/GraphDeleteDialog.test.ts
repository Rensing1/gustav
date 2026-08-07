import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import GraphDeleteDialog from "./GraphDeleteDialog.svelte";

describe("GraphDeleteDialog", () => {
  it("shows the exact cascading consequences and explicit confirmation", () => {
    render(GraphDeleteDialog, {
      props: {
        impact: {
          kind: "phase",
          id: "phase-1",
          title: "Grundlagen",
          modulesCount: 2,
          materialsCount: 6,
          tasksCount: 8,
          connectionsCount: 3
        },
        action: "?/deletePhase",
        error: null,
        onCancel: vi.fn()
      }
    });

    expect(screen.getByRole("dialog", { name: "Phase löschen" })).toBeInTheDocument();
    expect(screen.getByText("Grundlagen")).toBeInTheDocument();
    expect(screen.getByText("2 Module")).toBeInTheDocument();
    expect(screen.getByText("6 Materialien")).toBeInTheDocument();
    expect(screen.getByText("8 Aufgaben")).toBeInTheDocument();
    expect(screen.getByText("3 Verbindungen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abbrechen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Phase und Inhalte löschen" })).toBeInTheDocument();
    expect(document.querySelector('input[name="confirmed"]')).toHaveValue("1");
  });

  it("cancels safely with Escape and backdrop click", async () => {
    const onCancel = vi.fn();
    render(GraphDeleteDialog, {
      props: {
        impact: {
          kind: "module",
          id: "module-1",
          title: "Start",
          modulesCount: 1,
          materialsCount: 0,
          tasksCount: 1,
          connectionsCount: 0
        },
        action: "?/deleteModule",
        error: null,
        onCancel
      }
    });

    await fireEvent.keyDown(window, { key: "Escape" });
    await fireEvent.click(screen.getByRole("button", { name: "Löschdialog schließen" }));

    expect(onCancel).toHaveBeenCalledTimes(2);
  });
});
