import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import GraphInspectorPanel from "./GraphInspectorPanel.svelte";

describe("GraphInspectorPanel", () => {
  it("renders an inline inspector shell for graph entities", () => {
    render(GraphInspectorPanel, {
      props: {
        eyebrow: "Property inspector",
        title: "Phase bearbeiten"
      }
    });

    expect(screen.getByText("Property inspector")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Phase bearbeiten" })).toBeInTheDocument();
  });
});
