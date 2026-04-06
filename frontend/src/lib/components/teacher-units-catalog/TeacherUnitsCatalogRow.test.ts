import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherUnitsCatalogRow from "./TeacherUnitsCatalogRow.svelte";

describe("TeacherUnitsCatalogRow", () => {
  it("renders title, topic, meta and a formatted update label", () => {
    render(TeacherUnitsCatalogRow, {
      props: {
        unit: {
          id: "unit-1",
          title: "Wie soll der Staat handeln?",
          topic: "Mehr Staat in der Krise",
          meta: "Modular · In Bearbeitung",
          updated_at: "2026-04-06T09:30:00+00:00",
          href: "/teaching/units/unit-1"
        }
      }
    });

    expect(screen.getByRole("link", { name: /wie soll der staat handeln/i })).toHaveAttribute(
      "href",
      "/teaching/units/unit-1"
    );
    expect(screen.getByText("Mehr Staat in der Krise")).toBeInTheDocument();
    expect(screen.getByText("Modular · In Bearbeitung")).toBeInTheDocument();
    expect(screen.getByText(/aktualisiert/i)).toBeInTheDocument();
  });
});
