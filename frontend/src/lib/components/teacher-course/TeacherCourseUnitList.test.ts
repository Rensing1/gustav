import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherCourseUnitList from "./TeacherCourseUnitList.svelte";

const units = [
  { id: "unit-1", module_id: "module-1", title: "Erste Einheit", position: 1, href: "/teaching/units/unit-1" },
  { id: "unit-2", module_id: "module-2", title: "Zweite Einheit", position: 2, href: "/teaching/units/unit-2" }
];

describe("TeacherCourseUnitList", () => {
  it("renders a focused empty state without ordering controls", () => {
    render(TeacherCourseUnitList, {
      props: { units: [], canMutate: true }
    });

    expect(screen.getByText("Noch keine Lerneinheiten")).toBeInTheDocument();
    expect(screen.queryByText("Reihenfolge speichern")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Reihenfolge von/)).not.toBeInTheDocument();
  });

  it("does not offer ordering for a single unit or a read-only course", () => {
    const { unmount } = render(TeacherCourseUnitList, {
      props: { units: units.slice(0, 1), canMutate: true }
    });

    expect(screen.getByRole("link", { name: "Erste Einheit" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/Reihenfolge von/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nach unten" })).not.toBeInTheDocument();

    unmount();
    render(TeacherCourseUnitList, {
      props: { units, canMutate: false }
    });

    expect(screen.queryByLabelText(/Reihenfolge von/)).not.toBeInTheDocument();
    expect(screen.queryByText("Entfernen")).not.toBeInTheDocument();
  });

  it("shows save and discard only after the order changes", async () => {
    render(TeacherCourseUnitList, {
      props: { units, canMutate: true }
    });

    expect(screen.queryByText("Reihenfolge speichern")).not.toBeInTheDocument();

    const firstRow = screen.getByRole("listitem", { name: "Erste Einheit" });
    await fireEvent.click(within(firstRow).getByRole("button", { name: "Nach unten" }));

    expect(screen.getByText("Reihenfolge speichern")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Verwerfen" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")[0]).toHaveAccessibleName("Zweite Einheit");

    await fireEvent.click(screen.getByRole("button", { name: "Verwerfen" }));
    expect(screen.queryByText("Reihenfolge speichern")).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")[0]).toHaveAccessibleName("Erste Einheit");
  });

  it("restores a failed server draft and keeps its error beside the actions", () => {
    render(TeacherCourseUnitList, {
      props: {
        units,
        canMutate: true,
        draftModuleIds: ["module-2", "module-1"],
        reorderError: "Die Reihenfolge konnte nicht gespeichert werden."
      }
    });

    expect(screen.getAllByRole("listitem")[0]).toHaveAccessibleName("Zweite Einheit");
    expect(screen.getByRole("alert")).toHaveTextContent("Die Reihenfolge konnte nicht gespeichert werden.");
    expect(screen.getByText("Reihenfolge speichern")).toBeInTheDocument();
  });
});
