import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import TeacherGraphCommandBar from "./TeacherGraphCommandBar.svelte";

describe("TeacherGraphCommandBar", () => {
  it("renders command actions and an attached secondary area for popovers", () => {
    render(TeacherGraphCommandBar, {
      props: {
        actions: [
          { label: "Phase hinzufügen", href: "/teaching/units/unit-1?create-phase=1", active: true },
          { label: "Modul hinzufügen", href: "/teaching/units/unit-1?create-module=1", active: false }
        ]
      },
      context: new Map()
    });

    expect(screen.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeInTheDocument();
    expect(screen.getByText("Struktur")).toBeInTheDocument();
    expect(screen.getByText("Lernweg bearbeiten")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Phase hinzufügen" })).toHaveClass("workspace-top-action--active");
    expect(screen.getByRole("link", { name: "Modul hinzufügen" })).toHaveAttribute(
      "href",
      "/teaching/units/unit-1?create-module=1"
    );
  });

  it("renders local command actions as buttons", async () => {
    const openModuleDialog = vi.fn();

    render(TeacherGraphCommandBar, {
      props: {
        actions: [
          { label: "Modul hinzufügen", active: false, onClick: openModuleDialog }
        ]
      },
      context: new Map()
    });

    const button = screen.getByRole("button", { name: "Modul hinzufügen" });

    await fireEvent.click(button);

    expect(openModuleDialog).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("link", { name: "Modul hinzufügen" })).not.toBeInTheDocument();
  });
});
