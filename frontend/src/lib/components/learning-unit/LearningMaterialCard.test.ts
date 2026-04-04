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

    expect(screen.getByRole("heading", { name: "Überschrift" })).toBeInTheDocument();
    expect(screen.getByText("Wichtiger", { exact: false })).toBeInTheDocument();
    expect(document.querySelector("pre")).toBeNull();
  });
});
