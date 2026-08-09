import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import Page from "./+page.svelte";
import type { PageData } from "./$types";

function courseData(overrides: Partial<PageData["course"]> = {}): PageData {
  return {
    theme: "light",
    bootstrap: null,
    appSessionActive: false,
    assignedUnits: [
      { id: "unit-1", module_id: "module-1", title: "Netzwerke verstehen", position: 1, href: "/teaching/units/unit-1" },
      { id: "unit-2", module_id: "module-2", title: "Protokolle untersuchen", position: 2, href: "/teaching/units/unit-2" }
    ],
    availableUnits: [{ id: "unit-3", title: "Daten sicher übertragen" }],
    breadcrumbs: [{ label: "Kurse", href: "/teaching/courses" }],
    course: {
      id: "course-1",
      title: "10Fb Informatik",
      subject: "Informatik",
      grade_level: "10",
      term: null,
      school_year_start: 2026,
      status: "active",
      metadata_complete: true,
      ...overrides
    },
    deletionImpact: null,
    hidePageHeading: true,
    memberSearchQuery: "",
    memberSearchResults: [],
    members: [
      { sub: "student-1", name: "Alex Beispiel", joined_at: "2026-08-01T09:00:00Z", href: "/diagnostics/learners/student-1" }
    ],
    pageCopy: "1 Mitglieder · 2 Lerneinheiten",
    pageTitle: "10Fb Informatik",
    showAddMemberDialog: false,
    showAddUnitDialog: false,
    showCourseDrawer: false,
    showMembersDrawer: false,
    wideWorkspaceShell: true
  };
}

describe("teacher course detail page", () => {
  it("shows one unit action and no arbitrary member preview", async () => {
    render(Page, { props: { data: courseData(), form: {} as never } });

    expect(screen.getAllByRole("link", { name: "Lerneinheit hinzufügen" })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "KI-Nutzung öffnen" })).toHaveAttribute(
      "href",
      "/teaching/courses/course-1/ai-usage"
    );
    expect(screen.queryByText("Alex Beispiel")).not.toBeInTheDocument();
    expect(screen.getByText(/Informatik · Jahrgang 10 · 2026\/27/)).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Mitglieder verwalten" }));
    const drawer = screen.getByRole("dialog", { name: "Mitglieder verwalten" });
    expect(within(drawer).getByRole("link", { name: "Mitglied hinzufügen" })).toBeInTheDocument();
    expect(within(drawer).queryByRole("link", { name: "Mitgliederseite" })).not.toBeInTheDocument();
  });

  it("closes the members drawer with Escape or the outside surface", async () => {
    render(Page, { props: { data: courseData(), form: {} as never } });

    await fireEvent.click(screen.getByRole("button", { name: "Mitglieder verwalten" }));
    const drawer = screen.getByRole("dialog", { name: "Mitglieder verwalten" });
    await fireEvent.click(within(drawer).getByPlaceholderText("Name eingeben"));
    expect(drawer).toBeInTheDocument();

    await fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Mitglieder verwalten" })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Mitglieder verwalten" }));
    await fireEvent.click(screen.getByRole("button", { name: "Seitenleiste schließen" }));
    expect(screen.queryByRole("dialog", { name: "Mitglieder verwalten" })).not.toBeInTheDocument();
  });

  it("reopens the course drawer immediately after closing it", async () => {
    const data = courseData();
    data.showCourseDrawer = true;
    render(Page, { props: { data, form: {} as never } });

    expect(screen.getByRole("dialog", { name: "Kurs bearbeiten" })).toBeInTheDocument();
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Kurs bearbeiten" })).not.toBeInTheDocument();

    const editLink = screen.getByRole("link", { name: "Kurs bearbeiten" });
    editLink.addEventListener("click", (event) => event.preventDefault(), { once: true });
    await fireEvent.click(editLink);
    expect(screen.getByRole("dialog", { name: "Kurs bearbeiten" })).toBeInTheDocument();
  });

  it("names all missing metadata and blocks course mutations", async () => {
    render(Page, {
      props: {
        data: courseData({ subject: null, grade_level: null, school_year_start: null, metadata_complete: false }),
        form: {} as never
      }
    });

    expect(screen.getByText("Kursdaten unvollständig:").closest("section")).toHaveTextContent(
      "Kursdaten unvollständig: Fach, Jahrgang, Schuljahr"
    );
    expect(screen.queryByRole("link", { name: "Lerneinheit hinzufügen" })).not.toBeInTheDocument();
    expect(screen.queryByText("Nicht gesetzt")).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Mitglieder ansehen" }));
    const drawer = screen.getByRole("dialog", { name: "Mitglieder ansehen" });
    expect(within(drawer).queryByRole("link", { name: "Mitglied hinzufügen" })).not.toBeInTheDocument();
    expect(within(drawer).queryByRole("button", { name: "Entfernen" })).not.toBeInTheDocument();
  });

  it("renders archived courses read-only and loads real deletion impact in the settings drawer", () => {
    const data = courseData({ status: "archived" });
    data.showCourseDrawer = true;
    data.deletionImpact = {
      course_id: "course-1",
      title: "10Fb Informatik",
      members_count: 1,
      submissions_count: 7,
      dialogs_count: 2,
      files_count: 3
    };

    render(Page, { props: { data, form: {} as never } });

    expect(screen.getByText("Archiviert · schreibgeschützt")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Lerneinheit hinzufügen" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "KI-Nutzung öffnen" })).toHaveAttribute(
      "href",
      "/teaching/courses/course-1/ai-usage"
    );
    expect(screen.getByRole("link", { name: "Kurs bearbeiten" })).toHaveAttribute("href", "?course=1");
    expect(screen.getByText(/1 Mitgliedschaften, 7 Abgaben, 2 Dialoge und 3 Dateien/)).toBeInTheDocument();
  });
});
