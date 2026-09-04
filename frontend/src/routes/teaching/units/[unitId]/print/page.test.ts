import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "./+page.svelte";
import type { TeacherUnitPrintableContent } from "$lib/types/home";

const data = {
  theme: "light",
  bootstrap: null,
  appSessionActive: false,
  breadcrumbs: [],
  pageTitle: "Druckfassung erstellen",
  pageCopy: "",
  printable: {
    unit: { id: "unit-1", title: "Netzwerke verstehen", unit_type: "linear" },
    linear_sections: [
      {
        id: "section-1",
        kind: "section",
        title: "Einstieg",
        position: 1,
        materials: [
          {
            id: "material-1",
            content_type: "material",
            kind: "markdown",
            label: "Merkblatt",
            position: 1,
            mime_type: null,
            filename_original: null,
            size_bytes: null
          }
        ],
        tasks: [
          {
            id: "task-1",
            content_type: "task",
            kind: "native",
            label: "Erkläre das Netzwerk.",
            position: 1,
            mime_type: null,
            filename_original: null,
            size_bytes: null
          }
        ]
      }
    ],
    modular_phases: [],
    limits: {
      max_selected_items: 200,
      max_source_bytes: 52_428_800,
      max_output_bytes: 52_428_800,
      max_pages: 200
    }
  } as TeacherUnitPrintableContent
};

describe("teacher printable-unit page", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("starts empty and supports hierarchical selection before download", async () => {
    render(Page, { props: { data } as never });

    const form = screen.getByRole("form", { name: "Inhalte für die Druckfassung auswählen" });
    const download = within(form).getByRole("button", { name: "PDF herunterladen" });
    expect(within(form).getAllByRole("checkbox")).toHaveLength(4);
    expect(within(form).getAllByRole("checkbox").every((checkbox) => !checkbox.hasAttribute("checked"))).toBe(true);
    expect(download).toBeDisabled();
    expect(screen.getByText("0 von 2 Inhalten ausgewählt")).toBeInTheDocument();

    await fireEvent.click(within(form).getByRole("checkbox", { name: "Einstieg vollständig auswählen" }));

    expect(within(form).getByRole("checkbox", { name: "Merkblatt" })).toBeChecked();
    expect(within(form).getByRole("checkbox", { name: "Aufgabe: Erkläre das Netzwerk." })).toBeChecked();
    expect(screen.getByText("2 von 2 Inhalten ausgewählt")).toBeInTheDocument();
    expect(download).toBeEnabled();

    await fireEvent.click(within(form).getByRole("checkbox", { name: "Merkblatt" }));

    expect(screen.getByText("1 von 2 Inhalten ausgewählt")).toBeInTheDocument();
    expect(within(form).getByRole("checkbox", { name: "Einstieg vollständig auswählen" })).toHaveProperty(
      "indeterminate",
      true
    );
  });

  it("selects every module in a modular phase through the phase checkbox", async () => {
    const modular = structuredClone(data);
    modular.printable.unit.unit_type = "modular";
    modular.printable.linear_sections = [];
    modular.printable.modular_phases = [
      {
        id: "phase-1",
        title: "Erkunden",
        position: 1,
        modules: [
          { ...data.printable.linear_sections[0], id: "module-1", kind: "module", title: "Beobachten" },
          {
            ...data.printable.linear_sections[0],
            id: "module-2",
            kind: "module",
            title: "Erklären",
            materials: [{ ...data.printable.linear_sections[0].materials[0], id: "material-2", label: "Vertiefung" }],
            tasks: []
          }
        ]
      }
    ];

    render(Page, { props: { data: modular } as never });
    await fireEvent.click(screen.getByRole("checkbox", { name: "Phase Erkunden vollständig auswählen" }));

    expect(screen.getByRole("checkbox", { name: "Merkblatt" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Aufgabe: Erkläre das Netzwerk." })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Vertiefung" })).toBeChecked();
    expect(screen.getByText("3 von 3 Inhalten ausgewählt")).toBeInTheDocument();
  });

  it("shows a material-specific export error without leaving the selection page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json(
          { error: "material_unprintable", detail: "material_unprintable", material: { title: "Merkblatt" } },
          { status: 422 }
        )
      )
    );
    render(Page, { props: { data } as never });
    await fireEvent.click(screen.getByRole("checkbox", { name: "Merkblatt" }));
    await fireEvent.submit(screen.getByRole("form", { name: "Inhalte für die Druckfassung auswählen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Merkblatt");
    expect(screen.getByRole("button", { name: "PDF herunterladen" })).toBeEnabled();
  });
});
