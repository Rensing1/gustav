import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import GraphSelectionBar from "./GraphSelectionBar.svelte";

describe("GraphSelectionBar", () => {
  it("shows module context and keeps editing actions explicit", async () => {
    const openProperties = vi.fn();
    const requestDelete = vi.fn();

    render(GraphSelectionBar, {
      props: {
        selection: {
          kind: "module",
          title: "Partnerdebatten",
          phaseTitle: "Policy-Ebene",
          materialsCount: 1,
          tasksCount: 2,
          editorHref: "/teaching/units/unit-1/nodes/module-1"
        },
        onOpenProperties: openProperties,
        onRequestDelete: requestDelete
      }
    });

    expect(screen.getByRole("region", { name: "Ausgewähltes Modul" })).toHaveTextContent("Partnerdebatten");
    expect(screen.getByRole("region", { name: "Ausgewähltes Modul" })).toHaveTextContent("Policy-Ebene");
    expect(screen.getByText("1 Material · 2 Aufgaben")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inhalt bearbeiten" })).toHaveAttribute(
      "href",
      "/teaching/units/unit-1/nodes/module-1"
    );

    await fireEvent.click(screen.getByRole("button", { name: "Eigenschaften" }));
    expect(openProperties).toHaveBeenCalledTimes(1);
    expect(requestDelete).not.toHaveBeenCalled();
  });

  it("shows phase context with a direct module action", async () => {
    const openProperties = vi.fn();
    const addModule = vi.fn();

    render(GraphSelectionBar, {
      props: {
        selection: {
          kind: "phase",
          title: "Policy-Ebene",
          moduleCount: 5
        },
        onOpenProperties: openProperties,
        onAddModule: addModule,
        onRequestDelete: vi.fn()
      }
    });

    expect(screen.getByRole("region", { name: "Ausgewählte Phase" })).toHaveTextContent("5 Module");
    await fireEvent.click(screen.getByRole("button", { name: "Modul hinzufügen" }));
    expect(addModule).toHaveBeenCalledTimes(1);
  });
});
