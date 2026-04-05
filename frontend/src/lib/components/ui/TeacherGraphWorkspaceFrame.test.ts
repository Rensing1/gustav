import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherGraphWorkspaceFrame from "./TeacherGraphWorkspaceFrame.svelte";

describe("TeacherGraphWorkspaceFrame", () => {
  it("renders the shared teacher graph shell with commandbar", () => {
    render(TeacherGraphWorkspaceFrame, {
      props: {
        backHref: "/teaching/units",
        backLabel: "Zurück zu Lerneinheiten",
        title: "Programmieren mit Scratch",
        copy: "8 Phasen · 21 Module · dieselbe Graphansicht wie für Lernende",
        commandBarActions: [
          { label: "Phase hinzufügen", href: "/ui-lab", active: true },
          { label: "Modul hinzufügen", href: "/ui-lab", active: false }
        ]
      }
    });

    expect(screen.getByRole("link", { name: "Zurück zu Lerneinheiten" })).toHaveAttribute("href", "/teaching/units");
    expect(screen.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeInTheDocument();
    expect(screen.getByText("Teacher flow")).toBeInTheDocument();
  });
});
