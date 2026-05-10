import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherUnitsCatalogRow from "./TeacherUnitsCatalogRow.svelte";

describe("TeacherUnitsCatalogRow", () => {
  it("renders a title link with course names shortened to the first token", () => {
    render(TeacherUnitsCatalogRow, {
      props: {
        unit: {
          id: "unit-1",
          title: "Wie soll der Staat handeln?",
          topic: "Mehr Staat in der Krise",
          status_label: "In Bearbeitung",
          status_tone: "accent",
          courses_count: 2,
          courses: [
            { id: "course-1", title: "9L Informatik", href: "/teaching/courses/course-1" },
            { id: "course-2", title: "10b Politik", href: "/teaching/courses/course-2" }
          ],
          updated_at: "2026-04-06T09:30:00+00:00",
          href: "/teaching/units/unit-1"
        }
      }
    });

    expect(screen.getByRole("link", { name: /wie soll der staat handeln/i })).toHaveAttribute(
      "href",
      "/teaching/units/unit-1"
    );
    expect(screen.getByRole("link", { name: "Löschen" })).toHaveAttribute(
      "href",
      "/teaching/units/unit-1?delete=1"
    );
    expect(screen.getByText("Mehr Staat in der Krise")).toBeInTheDocument();
    expect(screen.queryByText("In Bearbeitung")).not.toBeInTheDocument();
    expect(screen.getByText("9L, 10b")).toBeInTheDocument();
    expect(screen.getByText(/aktualisiert/i)).toBeInTheDocument();
    expect(screen.queryByText(/modular/i)).not.toBeInTheDocument();
  });

  it("shows 'Ohne Kurs' when a unit is not assigned to any course", () => {
    render(TeacherUnitsCatalogRow, {
      props: {
        unit: {
          id: "unit-2",
          title: "Scratch",
          topic: null,
          status_label: "Entwurf",
          status_tone: "muted",
          courses_count: 0,
          courses: [],
          updated_at: "2026-04-06T08:30:00+00:00",
          href: "/teaching/units/unit-2"
        }
      }
    });

    expect(screen.getByText("Ohne Kurs")).toBeInTheDocument();
  });
});
