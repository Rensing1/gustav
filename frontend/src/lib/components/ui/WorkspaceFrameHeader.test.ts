import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import WorkspaceFrameHeader from "./WorkspaceFrameHeader.svelte";

describe("WorkspaceFrameHeader", () => {
  it("renders a technical workspace header with title and meta copy", () => {
    render(WorkspaceFrameHeader, {
      props: {
        eyebrow: "Taskfläche",
        title: "Erste Schritte",
        meta: "1 Modul geöffnet · Fokus auf Inhalte"
      }
    });

    expect(screen.getByText("Taskfläche")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Erste Schritte" })).toBeInTheDocument();
    expect(screen.getByText("1 Modul geöffnet · Fokus auf Inhalte")).toBeInTheDocument();
  });
});
