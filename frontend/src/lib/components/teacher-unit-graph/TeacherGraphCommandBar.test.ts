import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

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
    expect(screen.getByText("Canvas")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Phase hinzufügen" })).toHaveClass("workspace-top-action--active");
    expect(screen.getByRole("link", { name: "Modul hinzufügen" })).toHaveAttribute(
      "href",
      "/teaching/units/unit-1?create-module=1"
    );
  });
});
