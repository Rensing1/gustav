import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherNodeEditorSection from "./TeacherNodeEditorSection.svelte";

describe("TeacherNodeEditorSection", () => {
  it("shows the inline create area when requested", () => {
    render(TeacherNodeEditorSection, {
      props: {
        eyebrow: "Material",
        title: "Materialien",
        createLabel: "Material hinzufügen",
        showCreate: true
      }
    });

    expect(screen.getByRole("button", { name: "Material hinzufügen" })).toBeInTheDocument();
    expect(screen.getByText("Neu")).toBeInTheDocument();
    expect(screen.getByTestId("teacher-node-editor-create-slot")).toBeInTheDocument();
  });

  it("shows an empty message when there are no items and no open create form", () => {
    render(TeacherNodeEditorSection, {
      props: {
        eyebrow: "Aufgaben",
        title: "Aufgaben",
        createLabel: "Aufgabe hinzufügen",
        emptyMessage: "Noch keine Aufgaben hinterlegt.",
        showCreate: false,
        hasItems: false
      }
    });

    expect(screen.getByText("Noch keine Aufgaben hinterlegt.")).toBeInTheDocument();
    expect(screen.queryByTestId("teacher-node-editor-create-slot")).not.toBeInTheDocument();
  });
});
