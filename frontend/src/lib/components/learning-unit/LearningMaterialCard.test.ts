import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import LearningMaterialCard from "./LearningMaterialCard.svelte";

describe("LearningMaterialCard", () => {
  it("renders markdown materials as prose instead of a raw pre block", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-1",
          title: "Einführung",
          kind: "markdown",
          body_md: "## Überschrift\n\n**Wichtiger** Text."
        },
        expanded: true
      }
    });

    const toggle = screen.getByRole("button", { name: /einführung/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Einführung");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(screen.queryByText("Material")).toBeNull();
    expect(screen.getByRole("heading", { name: "Überschrift" })).toBeInTheDocument();
    expect(screen.getByText("Wichtiger", { exact: false })).toBeInTheDocument();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).toBeNull();
    expect(document.querySelector("pre")).toBeNull();
  });

  it("renders collapsed materials as a compact title row", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-2",
          title: "Sehr langer Materialtitel für die kompakte Zeile",
          kind: "markdown",
          body_md: "Inhalt"
        },
        contextLabel: "Modul Graphen",
        expanded: false
      }
    });

    const toggle = screen.getByRole("button", { name: /sehr langer materialtitel/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Sehr langer Materialtitel für die kompakte Zeile");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).not.toBeNull();
    expect(screen.queryByText("Modul Graphen")).toBeNull();
    expect(screen.queryByText("Material")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle-icon svg")).not.toBeNull();
  });
});
