import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$app/navigation", () => ({ replaceState: vi.fn() }));

import Page from "./+page.svelte";
import type { PageData } from "./$types";

const sampleData: PageData = {
  theme: "light",
  bootstrap: null,
  appSessionActive: false,
  breadcrumbs: [],
  hidePageHeading: true,
  wideWorkspaceShell: true,
  pageTitle: "Orientierung",
  contentSelection: { kind: "overview" },
  incomingPrerequisiteCount: 0,
  moduleDeletionImpact: {
    kind: "module",
    id: "node-1",
    title: "Orientierung",
    modulesCount: 1,
    materialsCount: 0,
    tasksCount: 0,
    connectionsCount: 0
  },
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
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("opens a modular node in a quiet overview without implicit create forms", () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    expect(screen.getByRole("heading", { name: "Inhalt auswählen" })).toBeInTheDocument();
    expect(screen.getByText("Wähle links ein Material oder eine Aufgabe aus.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Material hinzufügen$/i })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /^Aufgabe hinzufügen$/i })).toHaveLength(1);
    expect(screen.queryByLabelText("Materialtyp")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Aufgabentyp")).not.toBeInTheDocument();
  });

  it("returns from a new material draft to the mounted content outline", async () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    await fireEvent.click(screen.getAllByRole("button", { name: /^Material hinzufügen$/i })[0]);
    expect(screen.getByLabelText("Materialtyp")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "← Inhalte" }));

    expect(screen.queryByLabelText("Materialtyp")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inhalt auswählen" })).toBeInTheDocument();
  });

  it("starts with one criterion and allows up to ten criteria", async () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    await fireEvent.click(screen.getByRole("button", { name: /^Aufgabe hinzufügen$/i }));
    expect(screen.getAllByLabelText(/^Kriterium \d+$/i)).toHaveLength(1);
    for (let index = 1; index < 10; index += 1) {
      await fireEvent.click(screen.getByRole("button", { name: "Kriterium hinzufügen" }));
    }
    expect(screen.getAllByLabelText(/^Kriterium \d+$/i)).toHaveLength(10);
    expect(screen.queryByRole("button", { name: "Kriterium hinzufügen" })).not.toBeInTheDocument();
  });

  it("offers Filius task creation and labels existing Filius tasks", async () => {
    render(Page, {
      props: {
        data: {
          ...sampleData,
          editor: {
            ...sampleData.editor,
            tasks: [
              {
                id: "task-filius",
                kind: "filius",
                instruction_md: "Untersuche das Filius-Netzwerk.",
                criteria: [],
                teacher_context_md: null,
                due_at: null,
                max_attempts: null,
                position: 1,
                filius: {}
              }
            ]
          }
        },
        form: {} as never
      }
    });

    await fireEvent.click(screen.getByRole("button", { name: /^Aufgabe hinzufügen$/i }));

    const typeSelect = screen.getByLabelText("Aufgabentyp");
    expect(within(typeSelect).getByRole("option", { name: "Filius" })).toHaveValue("filius");

    await fireEvent.change(typeSelect, { target: { value: "filius" } });

    expect(screen.getByLabelText("Anweisung & Beschreibung")).toBeInTheDocument();
    expect(screen.getAllByLabelText(/^Kriterium \d+$/i)).toHaveLength(1);
    expect(screen.getByLabelText("Lehrkraft-Kontext")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /Untersuche das Filius-Netzwerk/i }));

    expect(screen.getAllByText("Filius").length).toBeGreaterThan(0);
    expect(screen.getByText("Lernende reichen hier ein Filius-Projekt als `.fls` ein.")).toBeInTheDocument();
  });

  it("shows every saved dialog field while keeping the preview closed", async () => {
    render(Page, {
      props: {
        data: {
          ...sampleData,
          editor: {
            ...sampleData.editor,
            tasks: [
              {
                id: "task-dialog",
                kind: "dialog",
                instruction_md: "Führe einen prüfenden Dialog.",
                criteria: ["Antworten sind begründet"],
                teacher_context_md: "Interner Fachkontext.",
                due_at: null,
                max_attempts: 3,
                position: 1,
                dialog: {
                  partner_name: "Dr. Dialog",
                  partner_description_md: "Eine sichtbare Kurzbeschreibung.",
                  role_md: "Stelle präzise Rückfragen.",
                  learning_goal_md: "Argumente begründet prüfen.",
                  opening_message_md: "Welche Position vertrittst du?",
                  response_mode: "hybrid",
                  max_rounds: 7,
                  closing_prompt_md: "Fasse dein Ergebnis zusammen."
                }
              }
            ]
          }
        },
        form: {} as never
      }
    });

    await fireEvent.click(screen.getByRole("button", { name: /Führe einen prüfenden Dialog/i }));

    expect(screen.getByLabelText("Anweisung & Beschreibung")).toHaveValue("Führe einen prüfenden Dialog.");
    expect(screen.getByLabelText("Lehrkraft-Kontext")).toHaveValue("Interner Fachkontext.");
    expect(screen.getByLabelText("Name des KI-Partners")).toHaveValue("Dr. Dialog");
    expect(screen.getByLabelText("Sichtbare Kurzbeschreibung")).toHaveValue("Eine sichtbare Kurzbeschreibung.");
    expect(screen.getByLabelText("Interne Rolleninstruktion")).toHaveValue("Stelle präzise Rückfragen.");
    expect(screen.getByLabelText("Internes Lernziel")).toHaveValue("Argumente begründet prüfen.");
    expect(screen.getByLabelText("Eröffnungsnachricht")).toHaveValue("Welche Position vertrittst du?");
    expect(screen.getByLabelText("Antwortmodus")).toHaveValue("hybrid");
    expect(screen.getByLabelText("Max. Schülerantworten")).toHaveValue(7);
    expect(screen.getByLabelText("Optionaler Abschlussauftrag")).toHaveValue("Fasse dein Ergebnis zusammen.");

    expect(screen.getByLabelText("Probeantwort eines Schülers")).not.toBeVisible();
    await fireEvent.click(screen.getByText("Gespeicherte Konfiguration testen"));
    expect(screen.getByLabelText("Probeantwort eines Schülers")).toBeVisible();
  });

  it("restores dialog task fields after a failed create action", () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {
          createTask: {
            error: "Bitte wähle zwischen 1 und 12 Dialogrunden.",
            values: {
              task_kind: "dialog",
              instruction_md: "Dialoganweisung",
              criteria_items: [],
              teacher_context_md: "Kontext",
              due_at: "",
              max_attempts: "",
              h5p_content_id: "",
              dialog_partner_name: "Gesprächspartner",
              dialog_partner_description_md: "Beschreibung",
              dialog_role_md: "Rolle",
              dialog_learning_goal_md: "Lernziel",
              dialog_opening_message_md: "Eröffnung",
              dialog_response_mode: "hybrid",
              dialog_max_rounds: "13",
              dialog_closing_prompt_md: "Abschluss"
            }
          }
        } as never
      }
    });

    expect(screen.getByLabelText("Aufgabentyp")).toHaveValue("dialog");
    expect(screen.getByLabelText("Name des KI-Partners")).toHaveValue("Gesprächspartner");
    expect(screen.getByLabelText("Antwortmodus")).toHaveValue("hybrid");
    expect(screen.getByLabelText("Max. Schülerantworten")).toHaveValue(13);
    expect(screen.getByText("Bitte wähle zwischen 1 und 12 Dialogrunden.")).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: /Arbeitsblatt/ })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Arbeitsblatt")).toBeInTheDocument();
    expect(screen.queryByText(/Datei vorbereitet:/i)).not.toBeInTheDocument();
  });

  it("shows a local accessible error when reordering fails", () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {
          reorderMaterial: { error: "Die Materialien konnten nicht neu geordnet werden." }
        } as never
      }
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Die Materialien konnten nicht neu geordnet werden.");
  });

  it("resynchronizes the local editor state when new page data arrives for the same route", async () => {
    const { rerender } = render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    expect(screen.getByRole("heading", { name: "Orientierung" })).toBeInTheDocument();

    await rerender({
      data: {
        ...sampleData,
        editor: {
          ...sampleData.editor,
          node: {
            ...sampleData.editor.node,
            title: "Orientierung aktualisiert",
            editor_title: "Orientierung aktualisiert"
          },
          materials: [
            {
              id: "material-2",
              title: "Merkblatt",
              kind: "markdown",
              body_md: "Neuer Inhalt",
              position: 1
            }
          ],
          tasks: [
            {
              id: "task-2",
              kind: "native",
              instruction_md: "Neue Aufgabe",
              criteria: ["Kriterium 1"],
              teacher_context_md: null,
              due_at: null,
              max_attempts: null,
              position: 1
            }
          ]
        }
      } satisfies PageData,
      form: {} as never
    });

    expect(screen.getByRole("heading", { name: "Orientierung aktualisiert" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Merkblatt/ })).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /Neue Aufgabe/i }));
    expect(screen.getByLabelText("Anweisung & Beschreibung")).toHaveValue("Neue Aufgabe");
    expect(screen.queryByRole("heading", { name: "Orientierung" })).not.toBeInTheDocument();
  });

  it("restores a scoped new-material draft after remounting in the same tab", async () => {
    const first = render(Page, { props: { data: sampleData, form: {} as never } });
    await fireEvent.click(screen.getAllByRole("button", { name: /^Material hinzufügen$/i })[0]);
    await fireEvent.input(screen.getByLabelText("Titel"), { target: { value: "Ungespeicherter Entwurf" } });
    expect(screen.getByRole("button", { name: "Verwerfen" })).toBeInTheDocument();
    await screen.findByRole("toolbar", { name: "Text formatieren" });
    first.unmount();

    render(Page, { props: { data: sampleData, form: {} as never } });

    expect(await screen.findByDisplayValue("Ungespeicherter Entwurf")).toBeInTheDocument();
  });

  it("asks for confirmation before deleting modular content", async () => {
    const data = {
      ...sampleData,
      editor: {
        ...sampleData.editor,
        materials: [{ id: "material-1", title: "Merkblatt", kind: "markdown" as const, body_md: "Inhalt", position: 1 }]
      }
    } satisfies PageData;
    render(Page, { props: { data, form: {} as never } });
    await fireEvent.click(screen.getByRole("button", { name: /Merkblatt/ }));
    await fireEvent.click(screen.getByText("Aktionen"));
    await fireEvent.click(screen.getByRole("button", { name: "Entfernen" }));

    const dialog = screen.getByRole("dialog", { name: "Material löschen" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("Merkblatt")).toBeInTheDocument();
    expect(document.querySelector('input[name="confirmed"]')).toHaveValue("1");
  });
});
