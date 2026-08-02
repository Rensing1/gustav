import { render, screen } from "@testing-library/svelte";
import { within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import UiPreviewSurface from "./UiPreviewSurface.svelte";

describe("UiPreviewSurface", () => {
  it("renders the internal preview with shell, content workspace, teacher graph references and feedback blocks", () => {
    render(UiPreviewSurface, {
      props: {
        userName: "Felix"
      }
    });

    expect(screen.getByRole("heading", { name: "Designsystem-Vorschau für GUSTAV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dark" })).toBeInTheDocument();
    expect(screen.getByText("Designreferenz")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Programmieren mit Scratch" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zurück zu Lerneinheiten" })).toHaveAttribute("href", "/teaching/units");
    expect(screen.getByRole("heading", { name: "Inhaltsverzeichnis" })).toBeInTheDocument();
    expect(screen.getByText("Was tut die Europäische Union für mich und wie verändert sie meinen Alltag?")).toBeInTheDocument();
    expect(screen.getByText("Werte der Union")).toBeInTheDocument();
    expect(screen.getByLabelText("Arbeitsfeld")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Klasse 10a" })).toHaveAttribute("href", "/learning");
    expect(screen.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeInTheDocument();
    expect(screen.getAllByText("Phase hinzufügen").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Eigenschaften" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Taskfläche").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Property inspector").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Abschnitt bearbeiten" })).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Erfolgreich abgemeldet" })).toBeInTheDocument();

    const learnerGraphCard = screen.getByText("Übersicht", { selector: ".preview-card__eyebrow" }).closest(".preview-card");
    expect(learnerGraphCard).not.toBeNull();
    if (!(learnerGraphCard instanceof HTMLElement)) {
      throw new Error("learner graph preview card missing");
    }
    const learnerScope = within(learnerGraphCard);
    expect(learnerScope.getByText("Offenes Modul")).toBeInTheDocument();
    expect(learnerScope.getByText("Weiteres offenes Modul")).toBeInTheDocument();
    expect(learnerScope.getByText("Abgeschlossen")).toBeInTheDocument();
    expect(learnerScope.getByText("Noch nicht offen")).toBeInTheDocument();
    expect(learnerScope.queryByText("Fertig")).toBeNull();
    expect(learnerScope.queryByText("Gesperrt")).toBeNull();
    expect(learnerScope.queryByText("Eigenschaften")).toBeNull();
    expect(learnerGraphCard.querySelectorAll(".teacher-flow-unit-node--selected")).toHaveLength(2);

    const teacherNodeCard = screen.getByText("Lehrkraft-Knoten", { selector: ".preview-card__eyebrow" }).closest(".preview-card");
    expect(teacherNodeCard).not.toBeNull();
    if (!(teacherNodeCard instanceof HTMLElement)) {
      throw new Error("teacher graph preview card missing");
    }
    expect(within(teacherNodeCard).getByText("Eigenschaften")).toBeInTheDocument();
  });
});
