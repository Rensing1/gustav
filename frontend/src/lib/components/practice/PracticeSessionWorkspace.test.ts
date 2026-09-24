import { cleanup, render, screen, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import PracticeSessionWorkspace from "./PracticeSessionWorkspace.svelte";

vi.mock("$app/navigation", () => ({ invalidateAll: vi.fn() }));
vi.mock("$lib/runtime/h5p-webcomponents", () => ({
  loadH5PWebcomponentsModule: vi.fn(async () => ({ defineElements: vi.fn() }))
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const session = {
  id: "session-1",
  mode: "due" as const,
  status: "active" as const,
  started_at: "2026-08-12T12:00:00Z",
  ended_at: null,
  end_reason: null,
  total_items: 2,
  completed_items: 0,
  summary: null,
  current_item: {
    id: "item-1",
    course_id: "course-1",
    practice_module_id: "module-1",
    module_title: "EVA-Prinzip",
    task_id: "task-1",
    position: 1,
    status: "feedback" as const,
    presentation_number: 1 as const,
    kind: "native" as const,
    instruction_md: "**Erkläre** das EVA-Prinzip.",
    h5p_content_id: null,
    latest_attempt_id: "attempt-1"
  }
};

describe("PracticeSessionWorkspace", () => {
  it.each([1, 2] as const)("explains only repeated presentation %s without changing progress", (presentationNumber) => {
    render(PracticeSessionWorkspace, { props: {
      session: { ...session, current_item: { ...session.current_item, presentation_number: presentationNumber } },
      attempt: null, attemptKey: "same-key", solution: null, nowIso: "2026-08-12T12:00:00Z"
    } });
    if (presentationNumber === 2) {
      expect(screen.getByText("Wiederholung", { exact: true })).toBeVisible();
      expect(screen.getByText("Du übst diese Aufgabe erneut. Deine bisherigen Antworten bleiben erhalten.")).toBeVisible();
    } else {
      expect(screen.queryByText("Wiederholung", { exact: true })).not.toBeInTheDocument();
    }
    expect(screen.getByRole("progressbar", { name: "50 Prozent bearbeitet" })).toHaveValue(1);
    expect(screen.getByRole("heading", { name: "Aufgabe 1 von 2" })).toBeVisible();
  });
  it("counts the current answered item in visible progress while feedback is shown", () => {
    render(PracticeSessionWorkspace, {
      props: {
        session,
        attempt: {
          id: "attempt-1",
          status: "completed",
          classification: "partial",
          fulfillment: 0.7,
          feedback_md: "Guter Anfang.",
          due_at: null
        },
        attemptKey: "key-1",
        solution: null,
        nowIso: "2026-08-12T12:00:00Z"
      }
    });

    expect(screen.getByRole("progressbar", { name: "50 Prozent bearbeitet" })).toHaveValue(1);
    expect(screen.getByText("Erkläre", { exact: false })).toBeVisible();
    expect(document.body.textContent).not.toContain("criteria");
  });

  it("allows a new submission after a technical analysis failure", () => {
    render(PracticeSessionWorkspace, {
      props: {
        session: {
          ...session,
          current_item: {
            ...session.current_item,
            status: "active"
          }
        },
        attempt: {
          id: "attempt-1",
          status: "failed",
          classification: null,
          fulfillment: null,
          feedback_md: null,
          due_at: null
        },
        attemptKey: "fresh-key",
        solution: null,
        nowIso: "2026-08-12T12:00:00Z"
      }
    });

    expect(screen.getByText("Die Auswertung konnte nicht abgeschlossen werden")).toBeVisible();
    expect(screen.getByLabelText("Deine Antwort")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Antwort prüfen" })).toBeEnabled();
  });

  it("separates the task from the responsive session context", () => {
    const { container } = render(PracticeSessionWorkspace, {
      props: {
        session,
        attempt: {
          id: "attempt-1",
          status: "completed",
          classification: "partial",
          fulfillment: 0.7,
          feedback_md: "Guter Anfang.",
          due_at: null
        },
        attemptKey: "key-1",
        solution: null,
        nowIso: "2026-08-12T12:00:00Z"
      }
    });

    const rail = screen.getByRole("complementary", { name: "Sitzungsfortschritt" });
    expect(container.querySelector(".practice-session__main")).toBeInTheDocument();
    expect(rail).toContainElement(screen.getByRole("progressbar"));
    expect(rail).toContainElement(screen.getByRole("button", { name: "Sitzung beenden" }));
  });

  it("keeps the H5P player visible until the learner consciously continues", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/h5p-context")) {
        return new Response(JSON.stringify({
          practice_completion_token: "token-1",
          context_id: "practice-context-1"
        }), { status: 201, headers: { "content-type": "application/json" } });
      }
      if (init?.method === "POST" && url.includes("/attempts")) {
        return new Response(JSON.stringify({ attempt_id: "attempt-1", status: "completed" }), {
          status: 202,
          headers: { "content-type": "application/json" }
        });
      }
      if (url.endsWith("/practice/attempts/attempt-1")) {
        return new Response(JSON.stringify({
          id: "attempt-1",
          status: "completed",
          classification: "secure",
          fulfillment: 1,
          feedback_md: "Volle Punktzahl erreicht.",
          due_at: null
        }), { status: 200, headers: { "content-type": "application/json" } });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(PracticeSessionWorkspace, { props: {
      session: {
        ...session,
        current_item: {
          ...session.current_item,
          status: "active",
          kind: "h5p",
          h5p_content_id: "content-1"
        }
      },
      attempt: null,
      attemptKey: "key-1",
      solution: null,
      nowIso: "2026-08-12T12:00:00Z"
    } });
    await waitFor(() => expect(document.querySelector("h5p-player")).toBeInTheDocument());

    document.querySelector("h5p-player")?.dispatchEvent(new CustomEvent("xAPI", { detail: { statement: {
      id: "statement-1",
      verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
      result: { completion: true, score: { raw: 1, max: 1 } }
    } } }));
    await tick();

    expect(await screen.findByText("Volle Punktzahl erreicht.")).toBeVisible();
    expect(document.querySelector("h5p-player")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Weiter zur nächsten Aufgabe/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Aufgabe überspringen" })).not.toBeInTheDocument();
  });

  it("still offers the next task when detailed H5P feedback cannot be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/h5p-context")) {
        return new Response(JSON.stringify({
          practice_completion_token: "token-1",
          context_id: "practice-context-1"
        }), { status: 201, headers: { "content-type": "application/json" } });
      }
      if (init?.method === "POST" && url.includes("/attempts")) {
        return new Response(JSON.stringify({ attempt_id: "attempt-1", status: "completed" }), {
          status: 202,
          headers: { "content-type": "application/json" }
        });
      }
      return new Response(JSON.stringify({ detail: "temporarily_unavailable" }), {
        status: 503,
        headers: { "content-type": "application/json" }
      });
    }));
    render(PracticeSessionWorkspace, { props: {
      session: {
        ...session,
        current_item: {
          ...session.current_item,
          status: "active",
          kind: "h5p",
          h5p_content_id: "content-1"
        }
      },
      attempt: null,
      attemptKey: "key-1",
      solution: null,
      nowIso: "2026-08-12T12:00:00Z"
    } });
    await waitFor(() => expect(document.querySelector("h5p-player")).toBeInTheDocument());
    document.querySelector("h5p-player")?.dispatchEvent(new CustomEvent("xAPI", { detail: { statement: {
      id: "statement-1",
      verb: { id: "https://adlnet.gov/expapi/verbs/completed" },
      result: { completion: true, score: { raw: 1, max: 1 } }
    } } }));

    expect(await screen.findByText("Ergebnis gespeichert")).toBeVisible();
    expect(screen.getByText(/ausführliche Einstufung konnte nicht geladen werden/)).toBeVisible();
    expect(screen.getByRole("button", { name: /Weiter zur nächsten Aufgabe/ })).toBeVisible();
    expect(document.querySelector("h5p-player")).toBeInTheDocument();
  });
});
