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
    expect(screen.getAllByText("Was tut die Europäische Union für mich und wie verändert sie meinen Alltag?").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Werte der Union").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("Aufgabe bearbeiten").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Klasse 10a" })).toHaveAttribute("href", "/learning");
    expect(screen.getByRole("toolbar", { name: "Graphwerkzeuge" })).toBeInTheDocument();
    expect(screen.getAllByText("Phase hinzufügen").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Eigenschaften" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Taskfläche zuerst/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Struktur").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Abschnitt bearbeiten" })).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "KI-Dialog · Gespräch" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "KI-Dialog · Abschluss" })).toBeInTheDocument();
    expect(screen.getAllByText("Gespräch mit Archivarin Ada").length).toBeGreaterThan(0);
    expect(screen.getByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Erfolgreich abgemeldet" })).toBeInTheDocument();

    const conversation = screen.getByTestId("preview-dialog-conversation");
    const conversationContext = within(conversation).getByRole("complementary", {
      name: "Aufgabe und Kontext"
    });
    const conversationComposer = within(conversation).getByRole("region", { name: "Beispielhafte Dialogeingabe" });
    expect(within(conversationContext).getByText("Aufgabe 2 · KI-Dialog")).toBeInTheDocument();
    expect(within(conversationContext).getByRole("region", { name: "Materialien" })).toBeInTheDocument();
    expect(within(conversation).getByRole("region", { name: "Gesprächsfortschritt" })).toHaveTextContent("Runde 1 von 3");
    expect(within(conversation).getByRole("article", { name: "Aktuelle Frage" })).toHaveTextContent(
      "Woran machst du diese Perspektive sprachlich fest?"
    );
    expect(within(conversationContext).queryByRole("button", { name: "Pausieren" })).toBeNull();
    expect(within(conversationContext).queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(conversationComposer).getByRole("button", { name: "Antwort senden" })).toBeInTheDocument();
    expect(within(conversationComposer).getByRole("button", { name: "Dialog beenden" })).toBeInTheDocument();
    expect(within(conversationComposer).getByRole("note")).toHaveTextContent("keine persönlichen oder vertraulichen Informationen");
    expect(within(conversationContext).queryByRole("note")).toBeNull();
    expect(within(conversationComposer).getByRole("button", { name: "Pausieren" })).toBeInTheDocument();

    const completion = screen.getByTestId("preview-dialog-completion");
    const completionContext = within(completion).getByRole("complementary", {
      name: "Aufgabe und Kontext"
    });
    const completionField = within(completion).getByRole("region", { name: "Abschluss vorbereiten" });
    expect(within(completionContext).queryByRole("button", { name: "Pausieren" })).toBeNull();
    expect(within(completionField).getByRole("button", { name: "Zurück zum Dialog" })).toBeInTheDocument();
    expect(within(completionField).getByRole("button", { name: "Endgültig abgeben" })).toBeInTheDocument();
    expect(within(completionField).getByRole("button", { name: "Pausieren" })).toBeInTheDocument();

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
