import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import PracticeFeedback from "./PracticeFeedback.svelte";

describe("PracticeFeedback", () => {
  it("renders sanitized feedback and relative scheduling without criteria", () => {
    render(PracticeFeedback, {
      props: {
        attempt: {
          id: "attempt-1",
          status: "completed",
          classification: "secure",
          fulfillment: 1,
          feedback_md: "**Das ist dir gelungen:** Berlin ist richtig.<script>alert(1)</script>",
          due_at: "2026-08-14T12:00:00.000Z"
        },
        sessionId: "session-1",
        itemId: "item-1",
        kind: "native",
        solution: null,
        nowIso: "2026-08-12T12:00:00.000Z"
      }
    });

    expect(screen.getByRole("heading", { name: "Sicher beantwortet" })).toBeVisible();
    expect(screen.getByText("Nächste Wiederholung in 2 Tagen")).toBeVisible();
    expect(screen.getByRole("button", { name: "Musterlösung ansehen" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Nächste Aufgabe" })).toBeVisible();
    expect(document.querySelector("script")).toBeNull();
    expect(document.body.textContent).not.toContain("Kriterien:");
  });
});
