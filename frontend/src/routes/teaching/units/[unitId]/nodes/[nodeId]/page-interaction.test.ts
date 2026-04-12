import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import Page from "./+page.svelte";
import type { PageData } from "./$types";

const sampleData: PageData = {
  theme: "light",
  bootstrap: null,
  breadcrumbs: [],
  hidePageHeading: true,
  pageTitle: "Orientierung",
  editor: {
    user: {
      sub: "teacher-1",
      name: "Felix",
      role: "teacher",
      roles: ["teacher"]
    },
    unit: {
      id: "unit-1",
      title: "Wie soll der Staat in...",
      unit_type: "modular",
      edit_href: "/teaching/units/unit-1"
    },
    node: {
      id: "node-1",
      kind: "module",
      title: "Orientierung",
      editor_title: "Orientierung",
      backing_section_id: "section-1"
    },
    settings: {
      kind: "module",
      required_prereq_count: 0
    },
    materials: [],
    tasks: []
  }
};

describe("teacher node editor page", () => {
  it("closes the create material area when the section button is clicked again", async () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    const materialsHeading = screen.getByRole("heading", { name: "Materialien" }).closest("section");
    expect(materialsHeading).not.toBeNull();
    const materialsSection = materialsHeading as HTMLElement;
    const toggleButton = within(materialsSection).getAllByRole("button", { name: /^Material hinzufügen$/i })[0];

    expect(within(materialsSection).getByText("Materialtyp")).toBeInTheDocument();

    await fireEvent.click(toggleButton);

    expect(within(materialsSection).queryByText("Materialtyp")).not.toBeInTheDocument();
  });

  it("renders ten visible criteria fields for task creation", () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    const tasksHeading = screen.getByRole("heading", { name: "Aufgaben" }).closest("section");
    expect(tasksHeading).not.toBeNull();
    const tasksSection = tasksHeading as HTMLElement;

    const fields = within(tasksSection).getAllByLabelText(/Kriterium \d+/i);
    expect(fields).toHaveLength(10);
  });

  it("shows a success message and the created material immediately after a successful create action", () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {
          createMaterial: {
            ok: true,
            message: "Material angelegt.",
            material_id: "material-1",
            editor: {
              ...sampleData.editor,
              materials: [
                {
                  id: "material-1",
                  title: "Arbeitsblatt",
                  kind: "file",
                  position: 1,
                  mime_type: "application/pdf",
                  size_bytes: 1024,
                  filename_original: "arbeitsblatt.pdf",
                  alt_text: "PDF Arbeitsblatt"
                }
              ]
            }
          }
        } as never
      }
    });

    expect(screen.getByText("Material angelegt.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Arbeitsblatt" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Arbeitsblatt")).toBeInTheDocument();
  });
});
