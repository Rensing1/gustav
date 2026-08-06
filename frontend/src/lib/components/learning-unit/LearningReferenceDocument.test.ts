import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import LearningReferenceDocument from "./LearningReferenceDocument.svelte";

describe("LearningReferenceDocument", () => {
  it("renders an accessible, collapsible material document", async () => {
    const onToggle = vi.fn();
    const onOpenReader = vi.fn();
    render(LearningReferenceDocument, {
      props: {
        referenceKey: "material:source",
        label: "Material · Aktuelles Modul",
        title: "Quellentext",
        material: {
          id: "source",
          title: "Quellentext",
          kind: "markdown",
          body_md: "## Abschnitt\n\nVollständiger Materialtext."
        },
        expanded: true,
        onToggle,
        onOpenReader
      }
    });

    const toggle = screen.getByRole("button", { name: "Quellentext ein- oder ausklappen" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAttribute("aria-controls", "reference-body-material-source");
    expect(toggle.querySelector(".learner-tree-chevron")).not.toBeNull();
    expect(toggle).not.toHaveTextContent(/[+−]/);
    expect(screen.getByText("Vollständiger Materialtext.")).toBeInTheDocument();

    await fireEvent.click(toggle);
    expect(onToggle).toHaveBeenCalledWith("material:source");
    await fireEvent.click(screen.getByRole("button", { name: "Quellentext groß lesen" }));
    expect(onOpenReader).toHaveBeenCalledWith("material:source");
  });

  it("shows file images directly with their accessible description", async () => {
    render(LearningReferenceDocument, {
      props: {
        referenceKey: "material:image",
        label: "Material · Aktuelles Modul",
        title: "Auswertungsgrafik",
        material: {
          id: "image",
          title: "Auswertungsgrafik",
          kind: "file",
          mime_type: "image/png",
          filename_original: "auswertung.png",
          file_url: "/api/materials/image",
          alt_text: "Balkendiagramm mit drei Ergebnissen"
        },
        expanded: true
      }
    });

    const image = screen.getByRole("img", { name: "Balkendiagramm mit drei Ergebnissen" });
    expect(image).toHaveAttribute("src", "/api/materials/image");
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveAttribute("decoding", "async");
    expect(screen.getByRole("link", { name: "Auswertungsgrafik separat öffnen" })).toHaveAttribute(
      "target",
      "_blank"
    );

    await fireEvent.error(image);
    expect(screen.getByText("Das Bild konnte nicht geladen werden.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Auswertungsgrafik separat öffnen" })).toBeInTheDocument();
  });

  it("shows the latest own image submission and keeps feedback and older attempts collapsed", () => {
    render(LearningReferenceDocument, {
      props: {
        referenceKey: "submission:task-old",
        label: "Eigene frühere Abgabe",
        title: "Frühere Bildanalyse",
        submissions: [
          {
            id: "submission-new",
            intent: "submit",
            attempt_nr: 2,
            kind: "image",
            created_at: "2026-08-03T10:00:00+00:00",
            analysis_status: "completed",
            files: [{ mime: "image/png", size: 2048, url: "/api/submissions/new" }],
            feedback_md: "Die Auswertung ist nachvollziehbar.",
            analysis_json: {
              schema: "criteria.v2",
              criteria_results: [{ criterion: "Begründung", explanation_md: "Gut belegt." }]
            }
          },
          {
            id: "submission-old",
            intent: "submit",
            attempt_nr: 1,
            kind: "text",
            created_at: "2026-08-02T10:00:00+00:00",
            analysis_status: "completed",
            text_body: "Mein erster Versuch."
          }
        ],
        expanded: true
      }
    });

    const document = screen.getByRole("article", { name: "Frühere Bildanalyse" });
    expect(within(document).getByRole("img", { name: "Eigene Bildabgabe zu Frühere Bildanalyse" })).toBeInTheDocument();
    expect(within(document).getByText(/Versuch 2/)).toBeInTheDocument();
    expect(within(document).getByText("Rückmeldung").closest("details")).not.toHaveAttribute("open");
    expect(within(document).getByText("Auswertung").closest("details")).not.toHaveAttribute("open");
    expect(within(document).getByText("Frühere Versuche").closest("details")).not.toHaveAttribute("open");
  });
});
