import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import DialogMessage from "./DialogMessage.svelte";

describe("DialogMessage", () => {
  it("marks only the current assistant question and sanitizes its markdown", async () => {
    const { container, rerender } = render(DialogMessage, {
      kind: "ai", speaker: "Archivarin Ada", markdown: "**Eine Frage** <script>alert(1)</script>", current: true
    });
    expect(screen.getByRole("article", { name: "Aktuelle Frage" })).toHaveClass("dialog-message--current");
    expect(screen.getByText("Archivarin Ada")).toHaveClass("dialog-message__speaker");
    expect(container.querySelector(".dialog-message__bubble strong")).toHaveTextContent("Eine Frage");
    expect(container.querySelector("script")).toBeNull();
    await rerender({ kind: "ai", speaker: "Archivarin Ada", markdown: "Eine frühere Frage", current: false });
    expect(screen.queryByRole("article", { name: "Aktuelle Frage" })).toBeNull();
  });

  it("renders a learner answer with a neutral avatar and optional starter note", () => {
    const { container } = render(DialogMessage, { kind: "student", markdown: "Meine Antwort", usedStarter: true });
    expect(screen.getByLabelText("Du")).toHaveTextContent("D");
    expect(screen.getByText("Hilfestellung: Satzanfang verwendet")).toBeInTheDocument();
    expect(container.querySelector(".dialog-message--student .dialog-message__bubble")).toHaveTextContent("Meine Antwort");
    expect(container.querySelector(".dialog-message__speaker")).toBeNull();
  });
});
