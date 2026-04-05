import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import UiPreviewSurface from "./UiPreviewSurface.svelte";

describe("UiPreviewSurface", () => {
  it("renders the internal preview with shell, teacher graph references, learner lists and feedback blocks", () => {
    render(UiPreviewSurface, {
      props: {
        userName: "Felix"
      }
    });

    expect(screen.getByRole("heading", { name: "Designsystem-Vorschau für GUSTAV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dark" })).toBeInTheDocument();
    expect(screen.getByText("Mistral Referenz")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Programmieren mit Scratch" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zurück zu Lerneinheiten" })).toHaveAttribute("href", "/teaching/units");
    expect(screen.getByRole("link", { name: "Klasse 10a" })).toHaveAttribute("href", "/learning");
    expect(screen.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeInTheDocument();
    expect(screen.getAllByText("Phase hinzufügen").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Eigenschaften" })).toBeInTheDocument();
    expect(screen.getByText("Taskfläche")).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Erfolgreich abgemeldet" })).toBeInTheDocument();
  });
});
