import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import LearningSubmissionWorkspace from "./LearningSubmissionWorkspace.svelte";
import type { LearningSubmission, LearningTask } from "$lib/types/learning";

const nativeTask: LearningTask = {
  id: "task-1",
  instruction_md: "Beschreibe die Lösung.",
  criteria: ["Kriterium"],
  kind: "native"
};

function feedbackSubmission(overrides: Partial<LearningSubmission> = {}): LearningSubmission {
  return {
    id: "submission-1",
    intent: "feedback",
    attempt_nr: 1,
    kind: "text",
    created_at: "2026-04-04T10:00:00+00:00",
    analysis_status: "completed",
    text_body: "Mein erster Entwurf",
    feedback_md: "Bitte strukturiere den Text klarer.",
    analysis_json: null,
    ...overrides
  };
}

describe("LearningSubmissionWorkspace", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("renders separate feedback and final submit actions in upload mode", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "upload"
      }
    });

    expect(screen.getByRole("button", { name: "Rückmeldung einholen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeInTheDocument();
    expect(screen.getByText("Datei auswählen")).toBeInTheDocument();
  });

  it("restores the server-selected upload mode together with its validation error", async () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "upload",
        errorMessage: "Bitte wähle eine Datei aus."
      }
    });

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: "Datei hochladen" })).toBeChecked();
    });
    expect(screen.getByText("Bitte wähle eine Datei aus.")).toBeVisible();
    expect(screen.getByLabelText("Datei auswählen")).toBeVisible();
  });

  it("uses the shared answer format choice and keeps both editors mounted", async () => {
    render(LearningSubmissionWorkspace, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "text"
      }
    });

    const group = screen.getByRole("group", { name: "Antwortform" });
    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await fireEvent.input(editor, { target: { value: "Entwurf bleibt erhalten" } });

    await fireEvent.click(screen.getByRole("radio", { name: "Datei hochladen" }));
    const upload = screen.getByLabelText("Datei auswählen") as HTMLInputElement;
    await fireEvent.change(upload, {
      target: { files: [new File(["dummy"], "quelle.pdf", { type: "application/pdf" })] }
    });

    await fireEvent.click(screen.getByRole("radio", { name: "Text schreiben" }));

    expect(group).toBeInTheDocument();
    expect(editor).toBeVisible();
    expect(editor.value).toBe("Entwurf bleibt erhalten");
    expect(upload).not.toBeVisible();
  });

  it("restores and persists text drafts scoped to the learner", async () => {
    const legacyKey = "gustav.learning.submission-draft:course-1:task-1:text";
    const scopedKey = "gustav.learning.submission-draft:student-2:course-1:task-1:text";
    window.localStorage.setItem(legacyKey, "Alter lokaler Entwurf");
    window.sessionStorage.setItem(legacyKey, "Fremder Sitzungsentwurf");
    window.sessionStorage.setItem(scopedKey, "Sitzungsentwurf");

    render(LearningSubmissionWorkspace, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "text"
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement | null;
    expect(editor).not.toBeNull();
    await waitFor(() => expect(editor!.value).toBe("Sitzungsentwurf"));

    await fireEvent.input(editor!, { target: { value: "Neuer Sitzungsentwurf" } });

    expect(window.sessionStorage.getItem("gustav.learning.submission-draft:course-1:task-1:text")).toBe(
      null
    );
    expect(window.sessionStorage.getItem(scopedKey)).toBe("Neuer Sitzungsentwurf");
    expect(window.localStorage.getItem(legacyKey)).toBeNull();
  });

  it("clears legacy text drafts and skips persistence when the learner is unknown", async () => {
    const legacyKey = "gustav.learning.submission-draft:course-1:task-1:text";
    window.sessionStorage.setItem(legacyKey, "Fremder Sitzungsentwurf");

    render(LearningSubmissionWorkspace, {
      props: {
        learnerSub: null,
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "text"
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement | null;
    expect(editor).not.toBeNull();
    await waitFor(() => expect(editor!.value).toBe(""));

    await fireEvent.input(editor!, { target: { value: "Nicht persistieren" } });

    expect(window.sessionStorage.getItem(legacyKey)).toBeNull();
    expect(Array.from({ length: window.sessionStorage.length }, (_value, index) => window.sessionStorage.key(index))).toEqual([]);
  });

  it("renders inline feedback when a feedback request has just completed", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialMode: "upload",
        initialHistoryLoaded: true,
        initialHistory: [feedbackSubmission()],
        message: "feedback"
      }
    });

    expect(screen.getByText("Neueste Rückmeldung")).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByText("Bitte strukturiere den Text klarer.")).toBeInTheDocument();
  });

  it("distinguishes feedback and final submissions in history", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission(),
          feedbackSubmission({
            id: "submission-2",
            intent: "submit",
            attempt_nr: 2,
            created_at: "2026-04-04T11:00:00+00:00",
            feedback_md: "Abgegeben."
          })
        ]
      }
    });

    const historyEntries = document.querySelectorAll(".learning-submission-history__entry");
    expect(historyEntries).toHaveLength(2);
    expect(within(historyEntries[0] as HTMLElement).getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(within(historyEntries[1] as HTMLElement).getAllByText("Abgabe").length).toBeGreaterThan(0);
  });

  it("does not fetch submission history when the course context is missing", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "undefined",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history"
      }
    });

    expect(await screen.findByText("Der Verlauf konnte nicht geladen werden. Bitte öffne die Lerneinheit erneut.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders markdown for submission, feedback and evaluation history in the learner workspace", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            text_body: "## Lösung\n\n**Antwort**<br>mit Umbruch\n\n1. Schritt\n2. Schritt\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
            feedback_md: "## Rückmeldung\n\n*Gut* gemacht.\n\n- Präzise",
            analysis_json: {
              schema: "learning.v1",
              score: 8,
              text: "Stabil",
              criteria_results: [
                {
                  criterion: "Kriterium",
                  explanation_md: "[Hinweis](https://example.com)\n\n| Name | Wert |\n| --- | --- |\n| A | B |"
                }
              ]
            }
          })
        ]
      }
    });

    expect(document.querySelector(".learning-submission-history .markdown-prose h2")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose strong")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose em")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose br")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose ol")).not.toBeNull();
    expect(document.querySelector(".learning-submission-history .markdown-prose table")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Hinweis" })).toHaveAttribute("href", "https://example.com");
  });

  it("renders completed native upload feedback without requiring text_body", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            kind: "image",
            text_body: null,
            mime_type: "image/png",
            files: [{ mime: "image/png", size: 2048, url: "https://example.com/upload.png" }],
            feedback_md: "## Rückmeldung\n\nDie Grafik ist gut lesbar.",
            analysis_json: {
              schema: "criteria.v2",
              score: 8,
              criteria_results: [{ criterion: "Anschaulichkeit", score: 8, max_score: 10, explanation_md: "Stimmige Darstellung." }]
            }
          })
        ]
      }
    });

    expect(screen.queryByText("Abgabe")).toBeNull();
    expect(screen.getByText("Datei")).toBeInTheDocument();
    expect(screen.getByText(/Die Grafik ist gut lesbar/i)).toBeInTheDocument();
    expect(screen.getByText(/Anschaulichkeit/)).toBeInTheDocument();
  });

  it("explains complex image feedback failures with a concrete retry hint", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: nativeTask,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            kind: "image",
            text_body: null,
            mime_type: "image/png",
            files: [{ mime: "image/png", size: 372528, url: "https://example.com/upload.png" }],
            feedback_md: null,
            analysis_status: "failed",
            error_code: "feedback_failed",
            feedback_last_error: "image_too_complex_for_provider"
          })
        ]
      }
    });

    expect(screen.getByText(/Das Bild ist wahrscheinlich zu groß oder zu komplex/i)).toBeInTheDocument();
    expect(screen.getByText(/nur die Zeichnung statt des ganzen Bildschirms/i)).toBeInTheDocument();
    expect(screen.queryByText("image_too_complex_for_provider")).toBeNull();
  });

  it("renders makecode hex history entries as curated code plus a download action", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: { ...nativeTask, kind: "calliope" },
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            kind: "file",
            text_body:
              '# makecode.evidence.v1\n\n## Summary\n\n- files_count: 2\n\n## Files\n\n### file: "main.ts"\n```typescript\nlet count = 1\n```\n\n### file: "main.py"\n```python\nprint("hi")\n```',
            files: [
              {
                mime: "application/x.makecode.hex",
                size: 2048,
                url: "https://example.com/upload.hex",
                download_url: "https://example.com/upload.hex?download=1"
              }
            ]
          })
        ]
      }
    });

    expect(screen.getByText('print("hi")')).toBeInTheDocument();
    expect(screen.queryByText("makecode.evidence.v1")).toBeNull();
    expect(screen.queryByText("let count = 1")).toBeNull();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute(
      "href",
      "https://example.com/upload.hex?download=1"
    );
  });

  it("renders scratch sb3 history entries as a structure view plus a download action", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: { ...nativeTask, kind: "scratch" },
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            kind: "file",
            text_body:
              "# scratch.evidence.v2\n\n## Summary\n- stage_present: true\n\n## Target Stage\n### Script 1\n- event_whenflagclicked\n- looks_say MESSAGE=\"Hallo\"",
            files: [
              {
                mime: "application/x.scratch.sb3",
                size: 4096,
                url: "https://example.com/upload.sb3",
                download_url: "https://example.com/upload.sb3?download=1"
              }
            ]
          })
        ]
      }
    });

    expect(document.querySelector(".structure-evidence")).not.toBeNull();
    expect(document.querySelector(".scratch-evidence")).not.toBeNull();
    expect(screen.queryByText("scratch.evidence.v2")).toBeNull();
    expect(screen.getByText("Target Stage")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute(
      "href",
      "https://example.com/upload.sb3?download=1"
    );
  });

  it("renders filius fls history entries as a structure view plus a download action", () => {
    render(LearningSubmissionWorkspace, {
      props: {
        courseId: "course-1",
        task: { ...nativeTask, kind: "filius" },
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        initialTab: "history",
        initialHistoryLoaded: true,
        initialHistory: [
          feedbackSubmission({
            kind: "file",
            text_body:
              "# filius.evidence.v1\n\n## Project\n- filius_version: 1.15.1\n\n## Ground Frame\n- class: filius.software.dhcp.DHCPServer",
            files: [
              {
                mime: "application/x.filius.fls",
                size: 4096,
                url: "https://example.com/upload.fls",
                download_url: "https://example.com/upload.fls?download=1"
              }
            ]
          })
        ]
      }
    });

    expect(document.querySelector(".structure-evidence")).not.toBeNull();
    expect(document.querySelector(".filius-evidence")).not.toBeNull();
    expect(screen.queryByText("filius.evidence.v1")).toBeNull();
    expect(screen.getByText("Ground Frame")).toBeInTheDocument();
    expect(screen.getByText(/filius\.software\.dhcp\.DHCPServer/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute(
      "href",
      "https://example.com/upload.fls?download=1"
    );
  });
});
