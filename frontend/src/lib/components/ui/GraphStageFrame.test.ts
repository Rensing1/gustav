import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import GraphStageFrame from "./GraphStageFrame.svelte";

describe("GraphStageFrame", () => {
  it("renders graph context before the canvas body", () => {
    render(GraphStageFrame, {
      props: {
        eyebrow: "Graph-Stage",
        title: "Lernpfad",
        copy: "Taskfläche zuerst, Graph daraus abgeleitet."
      }
    });

    expect(screen.getByText("Graph-Stage")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lernpfad" })).toBeInTheDocument();
    expect(screen.getByText("Taskfläche zuerst, Graph daraus abgeleitet.")).toBeInTheDocument();
  });

  it("can render without frame header chrome", () => {
    render(GraphStageFrame, {
      props: {
        eyebrow: "Graph-Stage",
        title: "Lernpfad",
        copy: "Taskfläche zuerst, Graph daraus abgeleitet.",
        chromeless: true
      }
    });

    expect(screen.queryByText("Graph-Stage")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Lernpfad" })).not.toBeInTheDocument();
    expect(screen.queryByText("Taskfläche zuerst, Graph daraus abgeleitet.")).not.toBeInTheDocument();
  });
});
