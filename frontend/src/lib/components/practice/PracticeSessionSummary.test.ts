import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import PracticeSessionSummary from "./PracticeSessionSummary.svelte";

const summary = {
  answered_items: 4,
  skipped_items: 1,
  pending_items: 0,
  classification_counts: { secure: 2, partial: 1, insufficient: 1 },
  next_due_at: "2026-08-14T12:00:00.000Z"
};

describe("PracticeSessionSummary", () => {
  it("celebrates a regular completion without points or grades", () => {
    render(PracticeSessionSummary, {
      props: { endReason: "completed", summary, nowIso: "2026-08-12T12:00:00.000Z" }
    });

    expect(screen.getByRole("heading", { name: "Übung geschafft" })).toBeVisible();
    expect(screen.getByText("Sicher").parentElement).toHaveTextContent("2");
    expect(screen.getByText("1 Aufgabe übersprungen")).toBeVisible();
    expect(screen.getByText("Nächste Wiederholung in 2 Tagen")).toBeVisible();
    expect(document.body.textContent).not.toMatch(/Punkte|Note|Prozent/);
  });

  it("uses neutral language for a deliberately stopped session", () => {
    render(PracticeSessionSummary, {
      props: { endReason: "stopped", summary, nowIso: "2026-08-12T12:00:00.000Z" }
    });

    expect(screen.getByRole("heading", { name: "Übung beendet" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Neue Übung auswählen" })).toHaveAttribute("href", "/learning/practice");
  });

  it("offers exam practice for an empty due snapshot", () => {
    render(PracticeSessionSummary, {
      props: {
        endReason: "empty",
        summary: { ...summary, answered_items: 0, skipped_items: 0, classification_counts: { secure: 0, partial: 0, insufficient: 0 }, next_due_at: null },
        nowIso: "2026-08-12T12:00:00.000Z"
      }
    });

    expect(screen.getByRole("heading", { name: "Heute ist nichts fällig" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Alle Aufgaben üben" })).toHaveAttribute("href", "/learning/practice?mode=exam");
  });
});
