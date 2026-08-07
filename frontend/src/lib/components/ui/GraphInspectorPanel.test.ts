import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import GraphInspectorPanel from "./GraphInspectorPanel.svelte";

describe("GraphInspectorPanel", () => {
  it("renders an inline inspector shell for graph entities", () => {
    render(GraphInspectorPanel, {
      props: {
        eyebrow: "Struktur",
        title: "Phase bearbeiten"
      }
    });

    expect(screen.getByText("Struktur")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Phase bearbeiten" })).toBeInTheDocument();
  });
});
