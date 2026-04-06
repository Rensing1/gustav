import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherUnitsCatalogList from "./TeacherUnitsCatalogList.svelte";

describe("TeacherUnitsCatalogList", () => {
  it("shows rows and the result count label", () => {
    render(TeacherUnitsCatalogList, {
      props: {
        activeViewLabel: "Zuletzt bearbeitet",
        resultCount: 2,
        items: [
          {
            id: "unit-1",
            title: "Europa",
            topic: "Krise",
            meta: "Modular",
            updated_at: "2026-04-06T09:30:00+00:00",
            href: "/teaching/units/unit-1"
          },
          {
            id: "unit-2",
            title: "Scratch",
            topic: null,
            meta: "Entwurf",
            updated_at: "2026-04-06T08:30:00+00:00",
            href: "/teaching/units/unit-2"
          }
        ]
      }
    });

    expect(screen.getByText("Zuletzt bearbeitet")).toBeInTheDocument();
    expect(screen.getByText("2 Einheiten")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /europa/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /scratch/i })).toBeInTheDocument();
  });

  it("shows a compact empty state", () => {
    render(TeacherUnitsCatalogList, {
      props: {
        activeViewLabel: "Zuletzt bearbeitet",
        resultCount: 0,
        items: []
      }
    });

    expect(screen.getByText("Noch keine passenden Lerneinheiten gefunden.")).toBeInTheDocument();
  });
});
