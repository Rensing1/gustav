import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherUnitsCatalogList from "./TeacherUnitsCatalogList.svelte";

describe("TeacherUnitsCatalogList", () => {
  it("shows the technical metabar and the table rows", () => {
    render(TeacherUnitsCatalogList, {
      props: {
        resultCount: 2,
        items: [
          {
            id: "unit-1",
            title: "Europa",
            topic: "Krise",
            status_label: "In Bearbeitung",
            status_tone: "accent",
            courses_count: 2,
            courses: [
              { id: "course-1", title: "10a", href: "/teaching/courses/course-1" },
              { id: "course-2", title: "10b", href: "/teaching/courses/course-2" }
            ],
            updated_at: "2026-04-06T09:30:00+00:00",
            href: "/teaching/units/unit-1"
          },
          {
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
        ]
      }
    });

    expect(screen.getByText(/Zeige 2 Einheiten/i)).toBeInTheDocument();
    expect(screen.queryByText("Status")).not.toBeInTheDocument();
    expect(screen.getAllByText("Kurse")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /europa/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /scratch/i })).toBeInTheDocument();
    expect(screen.getByText("Ohne Kurs")).toBeInTheDocument();
  });

  it("shows a compact empty state", () => {
    render(TeacherUnitsCatalogList, {
      props: {
        resultCount: 0,
        items: []
      }
    });

    expect(screen.getByText("Noch keine passenden Lerneinheiten gefunden.")).toBeInTheDocument();
  });
});
