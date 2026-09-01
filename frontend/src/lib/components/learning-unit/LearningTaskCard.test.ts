import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import { readWorkspaceCssBundle } from "$lib/styles/test-css-bundle";

import LearningTaskCard from "./LearningTaskCard.svelte";
import type { LearningTask } from "$lib/types/learning";

const task: LearningTask = {
  id: "task-1",
  instruction_md:
    "## Arbeitsauftrag\n\n**Erkläre** den *Zusammenhang*.<br>Nutze den Text.\n\n- Aspekt eins\n- Aspekt zwei\n\n1. Schritt eins\n2. Schritt zwei\n\n[Quelle](https://example.com)\n\n| Kriterium | Gewicht |\n| --- | --- |\n| Klarheit | 2 |",
  criteria: ["Klarheit"],
  kind: "native"
};
const validReviewedSubmissionId = "123e4567-e89b-42d3-a456-426614174099";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

describe("LearningTaskCard", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("binds the inline markdown editor to local draft state instead of a constant empty string", () => {
    const source = readFileSync(path.resolve(currentDir, "LearningTaskCard.svelte"), "utf8");

    expect(source).toContain("let draftText = $state(\"\")");
    expect(source).toContain("function updateDraft(value: string)");
    expect(source).toContain("value={draftText}");
    expect(source).toContain("onInput={updateDraft}");
    expect(source).not.toContain("value=\"\"");
    expect(source).not.toContain("onInput={() => {}}");
  });

  it("uses the shared choice switch once and removes the former tablist markup", () => {
    const source = readFileSync(path.resolve(currentDir, "LearningTaskCard.svelte"), "utf8");

    expect(source).toContain('import ChoiceSwitch from "$lib/components/ui/ChoiceSwitch.svelte";');
    expect(source.match(/<ChoiceSwitch/g)).toHaveLength(1);
    expect(source).not.toContain('role="tablist" aria-label="Bearbeitungsmodus"');
    expect(source).not.toContain('class="learning-task-inline-editor__mode-switch"');
  });

  it("restores and persists inline text drafts scoped to the learner", async () => {
    const legacyKey = "gustav.learning.submission-draft:course-1:task-1:text";
    const scopedKey = "gustav.learning.submission-draft:student-2:course-1:task-1:text";
    window.localStorage.setItem(legacyKey, "Alter Inline-Entwurf");
    window.sessionStorage.setItem(legacyKey, "Fremder Inline-Entwurf");
    window.sessionStorage.setItem(scopedKey, "Inline Sitzungsentwurf");

    render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task,
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        submissionFocused: true,
        initialSubmissionMode: "text"
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement | null;
    expect(editor).not.toBeNull();
    await waitFor(() => expect(editor!.value).toBe("Inline Sitzungsentwurf"));

    await fireEvent.input(editor!, { target: { value: "Inline neu" } });

    expect(window.sessionStorage.getItem(scopedKey)).toBe("Inline Sitzungsentwurf");
    await waitFor(() => expect(window.sessionStorage.getItem(scopedKey)).toBe("Inline neu"));
    expect(window.sessionStorage.getItem(legacyKey)).toBeNull();
    expect(window.localStorage.getItem(legacyKey)).toBeNull();
  });

  it("coalesces rapid draft writes and flushes the newest value when the page is hidden", async () => {
    const scopedKey = "gustav.learning.submission-draft:student-2:course-1:task-1:text";
    render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task,
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        submissionFocused: true,
        initialSubmissionMode: "text"
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor).toBeInTheDocument());
    const setItem = vi.spyOn(Storage.prototype, "setItem");

    await fireEvent.input(editor, { target: { value: "E" } });
    await fireEvent.input(editor, { target: { value: "En" } });
    await fireEvent.input(editor, { target: { value: "Entwurf" } });
    expect(setItem).not.toHaveBeenCalled();

    window.dispatchEvent(new Event("pagehide"));
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(setItem).toHaveBeenCalledWith(scopedKey, "Entwurf");
    expect(window.sessionStorage.getItem(scopedKey)).toBe("Entwurf");
    setItem.mockRestore();
  });

  it("restores only the draft belonging to the task after an in-place task switch", async () => {
    const firstTaskKey = "gustav.learning.submission-draft:student-2:course-1:task-1:text";
    const secondTaskKey = "gustav.learning.submission-draft:student-2:course-1:task-2:text";
    const secondTask: LearningTask = {
      ...task,
      id: "task-2",
      instruction_md: "## Zweiter Arbeitsauftrag\n\nBegründe deine Antwort."
    };
    window.sessionStorage.setItem(firstTaskKey, "Entwurf für Aufgabe 1");

    const { rerender } = render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 1",
        unitType: "modular",
        workspaceOnly: true,
        submissionFocused: true,
        initialSubmissionMode: "text"
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor.value).toBe("Entwurf für Aufgabe 1"));

    await rerender({
      learnerSub: "student-2",
      courseId: "course-1",
      task: secondTask,
      taskTitle: "Aufgabe 2",
      unitType: "modular",
      workspaceOnly: true,
      submissionFocused: true,
      initialSubmissionMode: "text"
    });

    await waitFor(() => expect(editor.value).toBe(""));
    await fireEvent.input(editor, { target: { value: "Entwurf für Aufgabe 2" } });
    expect(window.sessionStorage.getItem(firstTaskKey)).toBe("Entwurf für Aufgabe 1");
    expect(window.sessionStorage.getItem(secondTaskKey)).toBeNull();
    await waitFor(() => expect(window.sessionStorage.getItem(secondTaskKey)).toBe("Entwurf für Aufgabe 2"));

    await rerender({
      learnerSub: "student-2",
      courseId: "course-1",
      task,
      taskTitle: "Aufgabe 1",
      unitType: "modular",
      workspaceOnly: true,
      submissionFocused: true,
      initialSubmissionMode: "text"
    });

    await waitFor(() => expect(editor.value).toBe("Entwurf für Aufgabe 1"));
  });

  it("falls back to the latest submitted text and keeps feedback in the open editor", async () => {
    render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        initialSubmissionMode: "text",
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-08-09T12:34:52+00:00",
            analysis_status: "completed",
            text_body: "Mein bisheriger Entwurf",
            feedback_md: "Gut begonnen.",
            analysis_json: {
              schema: "criteria.v2",
              criteria_results: [{ criterion: "Klarheit", score: 7, max_score: 10 }]
            }
          }
        ]
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement | null;
    expect(editor).not.toBeNull();
    await waitFor(() => expect(editor!.value).toBe("Mein bisheriger Entwurf"));

    const answerFormat = screen.getByRole("group", { name: "Antwortform" });
    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(responseGroup.compareDocumentPosition(answerFormat) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(responseGroup).getByText("Rückmeldung").closest("details")).not.toHaveAttribute("open");
    expect(within(responseGroup).getByText("Kriterien im Detail").closest("details")).not.toHaveAttribute("open");
    expect(within(responseGroup).getByText("Meine Abgabe").closest("details")).not.toHaveAttribute("open");
    expect(screen.queryByRole("tab")).toBeNull();
  });

  it("hydrates an untouched editor when completed text feedback arrives after mount", async () => {
    const reviewedSubmissionId = "123e4567-e89b-42d3-a456-426614174010";
    const { rerender } = render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        initialSubmissionMode: "text",
        history: []
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor.value).toBe(""));

    await rerender({
      learnerSub: "student-2",
      courseId: "course-1",
      task: { ...task, has_submission: true },
      taskTitle: "Begriffe definieren",
      unitType: "linear",
      workspaceOnly: true,
      submissionFocused: true,
      initialSubmissionMode: "text",
      history: [
        {
          id: reviewedSubmissionId,
          attempt_nr: 1,
          kind: "text",
          intent: "feedback",
          created_at: "2026-09-01T08:00:00+00:00",
          analysis_status: "completed",
          text_body: "Später geladener geprüfter Entwurf",
          feedback_md: "Gut erklärt."
        }
      ]
    });

    await waitFor(() => expect(editor.value).toBe("Später geladener geprüfter Entwurf"));
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
    expect(document.querySelector<HTMLInputElement>('input[name="feedback_submission_id"]')?.value).toBe(
      reviewedSubmissionId
    );
  });

  it.each([
    ["divergent", "Mein lokaler Entwurf"],
    ["intentionally empty", ""]
  ])("protects a %s session draft when completed feedback arrives", async (_label, storedDraft) => {
    const scopedKey = "gustav.learning.submission-draft:student-2:course-1:task-1:text";
    window.sessionStorage.setItem(scopedKey, storedDraft);
    const { rerender } = render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        initialSubmissionMode: "text",
        history: []
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor.value).toBe(storedDraft));

    await rerender({
      learnerSub: "student-2",
      courseId: "course-1",
      task: { ...task, has_submission: true },
      taskTitle: "Begriffe definieren",
      unitType: "linear",
      workspaceOnly: true,
      submissionFocused: true,
      initialSubmissionMode: "text",
      history: [
        {
          id: "123e4567-e89b-42d3-a456-426614174011",
          attempt_nr: 1,
          kind: "text",
          intent: "feedback",
          created_at: "2026-09-01T08:00:00+00:00",
          analysis_status: "completed",
          text_body: "Geprüfter Entwurf",
          feedback_md: "Gut erklärt."
        }
      ]
    });

    await waitFor(() => expect(editor.value).toBe(storedDraft));
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
  });

  it("protects a local edit when completed feedback arrives after mount", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        initialSubmissionMode: "text",
        history: []
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await fireEvent.input(editor, { target: { value: "Gerade bearbeiteter Entwurf" } });

    await rerender({
      learnerSub: "student-2",
      courseId: "course-1",
      task: { ...task, has_submission: true },
      taskTitle: "Begriffe definieren",
      unitType: "linear",
      workspaceOnly: true,
      submissionFocused: true,
      initialSubmissionMode: "text",
      history: [
        {
          id: "123e4567-e89b-42d3-a456-426614174013",
          attempt_nr: 1,
          kind: "text",
          intent: "feedback",
          created_at: "2026-09-01T08:00:00+00:00",
          analysis_status: "completed",
          text_body: "Geprüfter Entwurf",
          feedback_md: "Gut erklärt."
        }
      ]
    });

    await waitFor(() => expect(editor.value).toBe("Gerade bearbeiteter Entwurf"));
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
  });

  it("omits the evaluation disclosure when the latest submission has no criteria results", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-08-09T12:34:52+00:00",
            analysis_status: "completed",
            text_body: "Mein Entwurf",
            feedback_md: "Gut begonnen."
          }
        ]
      }
    });

    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(within(responseGroup).getByText("Rückmeldung")).toBeInTheDocument();
    expect(within(responseGroup).getByText("Meine Abgabe")).toBeInTheDocument();
    expect(within(responseGroup).queryByText("Auswertung")).toBeNull();
  });

  it("disables final submission after the learner changes a reviewed text", async () => {
    render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-08-09T12:34:52+00:00",
            analysis_status: "completed",
            text_body: "Mein Entwurf",
            feedback_md: "Gut begonnen."
          }
        ]
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor.value).toBe("Mein Entwurf"));
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();

    await fireEvent.input(editor, { target: { value: "Mein überarbeiteter Entwurf" } });

    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
    const actions = screen.getByRole("region", { name: "Dein nächster Schritt" });
    expect(within(actions).getByText("Für diese Fassung zuerst Rückmeldung einholen.")).toBeInTheDocument();

    await fireEvent.input(editor, { target: { value: "  Mein Entwurf  " } });

    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
    expect(within(actions).queryByText("Für diese Fassung zuerst Rückmeldung einholen.")).toBeNull();
  });

  it("offers a retry when submission history failed to load", async () => {
    const onRetryHistory = vi.fn();
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        history: [],
        historyState: "failed",
        feedbackStatusMessage: "Der Verlauf konnte nicht geladen werden. Bitte versuche es erneut.",
        onRetryHistory
      }
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Der Verlauf konnte nicht geladen werden");
    expect(screen.queryByText("Für diese Fassung zuerst Rückmeldung einholen.")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(onRetryHistory).toHaveBeenCalledTimes(1);
  });

  it("does not offer finalization for a reviewed submission with an invalid id", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        history: [
          {
            id: "submission-feedback",
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-09-01T08:00:00+00:00",
            analysis_status: "completed",
            text_body: "Geprüfter Entwurf",
            feedback_md: "Gut erklärt."
          }
        ]
      }
    });

    expect(screen.queryByRole("button", { name: "Endgültig abgeben" })).toBeNull();
    expect(document.querySelector('input[name="finalization_idempotency_key"]')).toBeNull();
  });

  it("locks text and file inputs while feedback is being generated", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        workspaceOnly: true,
        submissionFocused: true,
        feedbackPending: true,
        pendingIntent: "feedback"
      }
    });

    expect(document.querySelector('textarea[aria-label="text_body"]')).toBeDisabled();
    expect(screen.getByLabelText("Datei auswählen")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rückmeldung einholen" })).toBeDisabled();
  });

  it("clears legacy inline drafts and skips persistence when the learner is unknown", async () => {
    const legacyKey = "gustav.learning.submission-draft:course-1:task-1:text";
    window.sessionStorage.setItem(legacyKey, "Fremder Inline-Entwurf");

    render(LearningTaskCard, {
      props: {
        learnerSub: null,
        courseId: "course-1",
        task,
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        submissionFocused: true,
        initialSubmissionMode: "text"
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement | null;
    expect(editor).not.toBeNull();
    await waitFor(() => expect(editor!.value).toBe(""));

    await fireEvent.input(editor!, { target: { value: "Nicht persistieren" } });

    expect(window.sessionStorage.getItem(legacyKey)).toBeNull();
    expect(Array.from({ length: window.sessionStorage.length }, (_value, index) => window.sessionStorage.key(index))).toEqual([]);
  });

  it("opens inline editing controls inside the task flow instead of a separate workspace", () => {
    const { container } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        submissionFocused: true,
        initialSubmissionMode: "upload"
      }
    });

    expect(screen.getByRole("button", { name: "Pausieren" })).toBeInTheDocument();
    expect(container.querySelector(".learning-task-inline-editor__header .workspace-label")).toBeNull();
    expect(screen.getByRole("heading", { name: "Arbeitsauftrag" })).toBeInTheDocument();
    expect(screen.getByText(/Erkläre/i, { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Datei auswählen")).toBeInTheDocument();
    expect(screen.queryByText("Arbeitsbereich")).toBeNull();
  });

  it("renders collapsed tasks as a compact title row", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 3",
        contextLabel: "Modul Graphen",
        unitType: "linear",
        expanded: false
      }
    });

    const toggle = screen.getByRole("button", { name: /aufgabe 3/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Aufgabe 3");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).not.toBeNull();
    expect(screen.getByText("Modul Graphen")).toBeInTheDocument();
    expect(document.querySelector(".learning-work-item__kicker")).not.toBeNull();
    expect(document.querySelector(".learning-work-item__toggle-icon svg")).not.toBeNull();
  });

  it("uses a compact modular task row with status and CTA before opening review or editing", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 3",
        contextLabel: "Modul Graphen",
        unitType: "modular",
        expanded: true,
        compactLayout: true
      }
    });

    expect(screen.getByText(/Arbeitsauftrag Erkläre den Zusammenhang/)).toBeInTheDocument();
    expect(screen.getByText("Weitere Angaben in der Aufgabe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aufgabe 3 beginnen" })).toBeInTheDocument();
    expect(screen.queryByText("Aufgabe offen")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Aufgabe 3" })).toBeNull();
    expect(document.querySelector(".learning-task-inline-editor")).toBeNull();
    expect(document.querySelector(".learning-task-row")).not.toBeNull();
    expect(document.querySelector(".learning-task-row__copy")).not.toBeNull();
    expect(document.querySelector(".learning-task-row__preview")).not.toBeNull();
    expect(document.querySelector(".learning-task-row__actions")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Pausieren" })).toBeNull();
  });

  it("does not show a truncation hint for a short complete task preview", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, instruction_md: "Nenne zwei Beispiele." },
        taskTitle: "Aufgabe 3",
        unitType: "modular",
        expanded: true,
        compactLayout: true
      }
    });

    expect(screen.getByText("Nenne zwei Beispiele.")).toBeInTheDocument();
    expect(screen.queryByText("Weitere Angaben in der Aufgabe")).toBeNull();
  });

  it("shows a truncation hint when a one-line source is visually clipped", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          instruction_md: "Vergleiche die beiden Darstellungen sorgfältig und begründe anschließend deine Entscheidung nachvollziehbar."
        },
        taskTitle: "Aufgabe 3",
        unitType: "modular",
        expanded: true,
        compactLayout: true
      }
    });

    const preview = document.querySelector(".learning-task-row__preview") as HTMLParagraphElement;
    Object.defineProperty(preview, "scrollHeight", { configurable: true, value: 60 });
    Object.defineProperty(preview, "clientHeight", { configurable: true, value: 32 });
    await fireEvent(window, new Event("resize"));

    await waitFor(() => expect(screen.getByText("Weitere Angaben in der Aufgabe")).toBeInTheDocument());
  });

  it("keeps the complete instruction in the workspace task surface", () => {
    const { container } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 3",
        unitType: "modular",
        expanded: true,
        compactLayout: true,
        workspaceOnly: true,
        submissionFocused: true
      }
    });

    const statement = screen.getByRole("region", { name: "Vollständige Aufgabenstellung" });
    expect(within(statement).getByRole("heading", { name: "Arbeitsauftrag" })).toBeInTheDocument();
    expect(within(statement).getByText("Aspekt zwei")).toBeInTheDocument();
    expect(container.querySelector(".learning-task-workspace-statement")).not.toBeNull();
  });

  it.each(["h5p", "visual"] as const)(
    "keeps the complete instruction in the compact %s task workspace",
    (kind) => {
      render(LearningTaskCard, {
        props: {
          courseId: "course-1",
          task: { ...task, kind, h5p: kind === "h5p" ? { content_id: null } : null },
          taskTitle: "Aufgabe 3",
          unitType: "modular",
          expanded: true,
          compactLayout: true,
          workspaceOnly: true,
          submissionFocused: true
        }
      });

      const statement = screen.getByRole("region", { name: "Vollständige Aufgabenstellung" });
      expect(within(statement).getByText("Aspekt zwei")).toBeInTheDocument();
    }
  );

  it("shows persisted draft affordances from task metadata before history is loaded", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          has_submission: true,
          latest_submission_intent: "feedback",
          latest_submission_analysis_status: "completed",
          latest_submission_created_at: "2026-04-21T09:00:00+00:00"
        },
        taskTitle: "Aufgabe 3",
        unitType: "modular",
        compactLayout: true,
        expanded: true,
        history: []
      }
    });

    expect(screen.getByRole("button", { name: "Entwurf weiterbearbeiten" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Meine Abgabe" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Endgültig abgeben" })).toBeNull();
    expect(document.querySelector(".learning-task-row--draft")).not.toBeNull();
  });

  it("keeps the compact task row visible while review and editor open underneath", async () => {
    const history = [
      {
        id: "submission-1",
        attempt_nr: 1,
        kind: "text" as const,
        intent: "submit" as const,
        created_at: "2026-04-07T12:10:00+00:00",
        analysis_status: "completed" as const,
        text_body: "Meine Lösung",
        feedback_md: "## Rückmeldung\n\nPasst.",
        analysis_json: {
          schema: "learning.v1",
          score: 8,
          text: "Stabil",
          criteria_results: []
        }
      }
    ];

    const { container, rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 3",
        unitType: "modular",
        compactLayout: true,
        expanded: true,
        reviewPanelOpen: true,
        history
      }
    });

    expect(document.querySelector(".learning-task-row")).not.toBeNull();
    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(responseGroup.querySelector(".learning-response-panel")).toHaveAttribute("open");
    expect(within(responseGroup).getByText("Meine Abgabe").closest("details")).not.toHaveAttribute("open");
    const editor = container.querySelector(".learning-task-inline-editor");
    expect(editor).not.toBeNull();
    expect(within(editor as HTMLElement).getByText(/Erkläre/i, { exact: false })).toBeInTheDocument();

    await rerender({
      courseId: "course-1",
      task,
      taskTitle: "Aufgabe 3",
      unitType: "modular",
      compactLayout: true,
      expanded: true,
      submissionFocused: true,
      reviewPanelOpen: false,
      history
    });

    expect(document.querySelector(".learning-task-row")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Pausieren" })).toBeInTheDocument();
    expect(screen.queryByText("Die Bearbeitung bleibt Teil derselben Arbeitsfläche.")).toBeNull();
    expect(document.querySelector(".learning-task-inline-editor__statement")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Arbeitsauftrag" })).toBeInTheDocument();
    const activeEditor = container.querySelector(".learning-task-inline-editor");
    expect(activeEditor).not.toBeNull();
    expect(within(activeEditor as HTMLElement).getByText(/Erkläre/i, { exact: false })).toBeInTheDocument();
  });

  it("styles the compact modular task row as a preview-plus-actions layout", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const designSystemCss = css;

    expect(css).toMatch(
      /\.learning-task-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto;[^}]*align-items:\s*center;/s
    );
    expect(css).toMatch(
      /\.learning-task-row__preview\s*\{[^}]*font-size:\s*calc\(0\.86rem \* var\(--learning-unit-font-scale\)\);[^}]*-webkit-line-clamp:\s*2;[^}]*white-space:\s*normal;[^}]*text-overflow:\s*ellipsis;/s
    );
    expect(css).toMatch(/\.learning-task-row__actions\s*\{[^}]*justify-content:\s*flex-end;[^}]*justify-self:\s*end;/s);
    expect(css).toMatch(/\.learning-task-row__more\s*\{[^}]*font-size:/s);
    expect(css).toMatch(/\.learning-task-workspace-statement\s*\{[^}]*display:\s*block;/s);
    expect(css).toMatch(/@container \(min-width:\s*60rem\)[\s\S]*\.learning-task-workspace-statement\s*\{[^}]*display:\s*none;/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-task-inline-editor__statement\s*\{[^}]*padding:\s*0;/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-task-inline-editor__statement\s*\{[^}]*border-left:\s*0;/s);
    expect(designSystemCss).toMatch(/\.learning-unit-content-shell \.learning-task-inline-editor__statement\s*\{[^}]*background:\s*transparent;/s);
    expect(designSystemCss).toMatch(/\.workspace-top-action--subtle,\s*\.workspace-link-action--subtle\s*\{[^}]*min-height:\s*1\.72rem;[^}]*padding:\s*0\.24rem 0\.58rem;[^}]*font-size:\s*0\.7rem;/s);
    expect(designSystemCss).toMatch(/\.workspace-top-action--subtle,\s*\.workspace-link-action--subtle\s*\{[^}]*box-shadow:\s*1px 1px 0/s);
    expect(designSystemCss).toMatch(/\.workspace-top-action--subtle:hover,[^}]*\.workspace-link-action--subtle:hover,[^}]*transform:\s*none;/s);
    expect(readFileSync(path.resolve(currentDir, "LearningTaskCard.svelte"), "utf8")).toContain("workspace-top-action--subtle");
  });

  it("falls back to the task title when the instruction markdown is empty", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, instruction_md: " \n\n " },
        taskTitle: "Aufgabe 8",
        unitType: "modular",
        expanded: true,
        compactLayout: true
      }
    });

    expect(screen.getByText("Aufgabe 8")).toBeInTheDocument();
  });

  it("renders markdown in the compact review summary for submission, feedback and evaluation", async () => {
    const history = [
      {
        id: "submission-1",
        attempt_nr: 1,
        kind: "text" as const,
        intent: "submit" as const,
        created_at: "2026-04-07T12:10:00+00:00",
        analysis_status: "completed" as const,
        text_body: "## Lösung\n\n**Antwort**<br>mit Umbruch\n\n1. Schritt\n2. Schritt\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
        feedback_md: "## Rückmeldung\n\n*Gut* gemacht.\n\n- Präzise",
        analysis_json: {
          schema: "learning.v1",
          score: 8,
          text: "Stabil",
          criteria_results: [
            {
              criterion: "Klarheit",
              score: 2,
              max_score: 2,
              explanation_md: "Siehe [Hinweis](https://example.com).\n\n| Kriterium | Wert |\n| --- | --- |\n| Klarheit | gut |"
            }
          ]
        }
      }
    ];

    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 3",
        unitType: "modular",
        compactLayout: true,
        expanded: true,
        reviewPanelOpen: true,
        history
      }
    });

    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(responseGroup.querySelector("details:last-child .markdown-prose h2")).not.toBeNull();
    expect(responseGroup.querySelector("details:last-child .markdown-prose strong")).not.toBeNull();
    expect(responseGroup.querySelector("details:last-child .markdown-prose br")).not.toBeNull();
    expect(responseGroup.querySelector("details:last-child .markdown-prose ol")).not.toBeNull();
    expect(responseGroup.querySelector("details:last-child .markdown-prose table")).not.toBeNull();
    expect(responseGroup.querySelector("details:first-child .markdown-prose em")).not.toBeNull();
    expect(responseGroup.querySelector("details:first-child .markdown-prose ul")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Hinweis" })).toHaveAttribute("href", "https://example.com");
    expect(responseGroup.querySelector(".learning-criterion__explanation.markdown-prose table")).not.toBeNull();
  });

  it("does not render empty response disclosures while submission history is still unavailable", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          has_submission: true,
          latest_submission_intent: "feedback",
          latest_submission_analysis_status: "completed",
          latest_submission_created_at: "2026-05-12T08:30:00+00:00"
        },
        taskTitle: "Filius-Auswertung",
        unitType: "modular",
        compactLayout: true,
        expanded: true,
        reviewPanelOpen: true,
        history: []
      }
    });

    expect(screen.queryByRole("region", { name: "Rückmeldung zu deiner Abgabe" })).toBeNull();
    expect(screen.queryByText("Es liegt noch keine Rückmeldung vor.")).toBeNull();
    expect(screen.queryByText("Es liegt noch keine Auswertung vor.")).toBeNull();
  });

  it("keeps the task header compact when expanded", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 4",
        contextLabel: "Modul Graphen",
        unitType: "linear",
        expanded: true
      }
    });

    const toggle = screen.getByRole("button", { name: "Modul Graphen Aufgabe 4" });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Aufgabe 4");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).toBeNull();
    expect(screen.getByText("Modul Graphen")).toBeInTheDocument();
    expect(document.querySelector(".learning-work-item__kicker")).not.toBeNull();
    expect(screen.getByText(/Erkläre/i, { exact: false })).toBeInTheDocument();
  });

  it("shows a primary CTA directly after the task prompt when no history exists", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        history: []
      }
    });

    expect(screen.getByText("Noch nicht abgegeben")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aufgabe 5 beginnen" })).toBeInTheDocument();
    expect(screen.queryByText("Nächster Schritt")).toBeNull();
    expect(screen.queryByText("Antwortstatus")).toBeNull();
    expect(screen.queryByRole("button", { name: "Meine Abgabe" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Abgabe" })).toBeNull();
  });

  it("uses one retry action instead of a competing submission entry", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-1",
            attempt_nr: 1,
            kind: "text",
            intent: "submit",
            created_at: "2026-04-05 10:00",
            analysis_status: "completed",
            text_body: "Meine Lösung",
            feedback_md: "## Rückmeldung\n\nGut gemacht.",
            analysis_json: {
              schema: "learning.v1",
              score: 8,
              text: "Stabil",
              criteria_results: [
                {
                  criterion: "Klarheit",
                  score: 8,
                  max_score: 10,
                  explanation_md: "Gut strukturiert."
                }
              ]
            }
          },
          {
            id: "submission-0",
            attempt_nr: 0,
            kind: "text",
            intent: "feedback",
            created_at: "2026-04-04 09:00",
            analysis_status: "completed",
            text_body: "Alter Versuch",
            feedback_md: "Frühere Rückmeldung",
            analysis_json: {
              schema: "learning.v1",
              score: 5,
              text: "Früher",
              criteria_results: []
            }
          }
        ]
      }
    });

    expect(screen.getByText("Final abgegeben am 2026-04-05 10:00")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Erneut bearbeiten" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Meine Abgabe" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Rückmeldung zu deiner Abgabe" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Weitere Versuche" })).toBeNull();
  });

  it("enables final submit in the editor when the current draft matches completed feedback", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-04-07T10:35:29+00:00",
            analysis_status: "completed",
            text_body: "Geprüfter Entwurf",
            feedback_md: "Gut gemacht."
          }
        ]
      }
    });

    expect(screen.getByText("Entwurf mit Rückmeldung vorhanden")).toBeInTheDocument();
    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor.value).toBe("Geprüfter Entwurf"));
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
  });

  it("binds final submission forms to the reviewed submission", async () => {
    const reviewedSubmissionId = "123e4567-e89b-42d3-a456-426614174000";
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        history: [
          {
            id: reviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-04-07T10:35:29+00:00",
            analysis_status: "completed",
            text_body: "Geprüfter Entwurf",
            feedback_md: "Gut gemacht."
          }
        ]
      }
    });

    await waitFor(() => expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled());
    const finalizationKeys = Array.from(
      document.querySelectorAll<HTMLInputElement>('input[name="finalization_idempotency_key"]')
    );
    const feedbackSubmissionIds = Array.from(
      document.querySelectorAll<HTMLInputElement>('input[name="feedback_submission_id"]')
    );
    expect(finalizationKeys).toHaveLength(1);
    expect(finalizationKeys.every((input) => input.value === `finalize-${reviewedSubmissionId}`)).toBe(true);
    expect(feedbackSubmissionIds).toHaveLength(1);
    expect(feedbackSubmissionIds.every((input) => input.value === reviewedSubmissionId)).toBe(true);
  });

  it("shows and locks the editor while a final submission is being processed", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        feedbackPending: true,
        pendingIntent: "submit",
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-04-07T10:35:29+00:00",
            analysis_status: "completed",
            text_body: "Geprüfter Entwurf",
            feedback_md: "Gut gemacht."
          }
        ]
      }
    });

    expect(screen.getByRole("status")).toHaveTextContent("Abgabe wird verarbeitet ...");
    expect(screen.getByRole("button", { name: "Rückmeldung erneut einholen" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
    expect(document.querySelector('textarea[aria-label="text_body"]')).toBeDisabled();
  });

  it("opens native tasks with one accessible answer format choice", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 8",
        unitType: "linear",
        expanded: true,
        submissionFocused: true
      }
    });

    expect(screen.getByRole("group", { name: "Antwortform" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Text schreiben" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Datei hochladen" })).not.toBeChecked();
    expect(screen.getByText("Deine Lösung")).toBeInTheDocument();
  });

  it("keeps the text draft and selected file while switching answer formats", async () => {
    render(LearningTaskCard, {
      props: {
        learnerSub: "student-2",
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 8",
        unitType: "linear",
        expanded: true,
        submissionFocused: true
      }
    });

    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await fireEvent.input(editor, { target: { value: "Mein erhaltener Entwurf" } });

    await fireEvent.click(screen.getByRole("radio", { name: "Datei hochladen" }));
    const input = screen.getByLabelText("Datei auswählen") as HTMLInputElement;
    const file = new File(["dummy"], "beleg.pdf", { type: "application/pdf" });
    await fireEvent.change(input, { target: { files: [file] } });

    await fireEvent.click(screen.getByRole("radio", { name: "Text schreiben" }));
    expect(editor.closest(".learning-submission-mode-panel")).not.toHaveAttribute("hidden");
    expect(editor.value).toBe("Mein erhaltener Entwurf");

    await fireEvent.click(screen.getByRole("radio", { name: "Datei hochladen" }));
    expect(screen.getByText("beleg.pdf")).toBeVisible();
    expect(screen.getAllByRole("group", { name: "Antwortform" })).toHaveLength(1);
    expect(screen.queryByRole("tablist", { name: "Bearbeitungsmodus" })).toBeNull();
  });

  it("renders upload-only tasks directly in the task-specific upload editor", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          id: "task-scratch",
          kind: "scratch"
        },
        taskTitle: "Scratch-Aufgabe",
        unitType: "linear",
        expanded: true,
        submissionFocused: true
      }
    });

    expect(screen.queryByRole("radio", { name: "Text schreiben" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Datei hochladen" })).toBeNull();
    expect(screen.getByText(".sb3-Datei auswählen")).toBeInTheDocument();
  });

  it("renders filius tasks directly in the fls upload editor", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          id: "task-filius",
          kind: "filius"
        },
        taskTitle: "Filius-Aufgabe",
        unitType: "linear",
        expanded: true,
        submissionFocused: true
      }
    });

    expect(screen.queryByRole("radio", { name: "Text schreiben" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Datei hochladen" })).toBeNull();
    expect(screen.getByText(".fls-Datei auswählen")).toBeInTheDocument();
  });

  it("shows a compact file card with only a subtle remove action after selecting a file", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 9",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        initialSubmissionMode: "upload"
      }
    });

    const input = screen.getByLabelText("Datei auswählen") as HTMLInputElement;
    const file = new File(["dummy"], "loesung.pdf", { type: "application/pdf" });

    await fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByText("loesung.pdf")).toBeInTheDocument();
    expect(screen.getByText(/PDF ·/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entfernen" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ersetzen" })).toBeNull();
    expect(readFileSync(path.resolve(currentDir, "LearningTaskCard.svelte"), "utf8")).toContain(
      'workspace-top-action workspace-top-action--quiet workspace-top-action--subtle'
    );
  });

  it("delegates upload feedback requests to a browser-side callback instead of submitting the file form", async () => {
    const onSubmitUploadFeedback = vi.fn(async () => {});

    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 9",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        initialSubmissionMode: "upload",
        onSubmitUploadFeedback
      }
    });

    const input = screen.getByLabelText("Datei auswählen") as HTMLInputElement;
    const file = new File(["dummy"], "loesung.pdf", { type: "application/pdf" });

    await fireEvent.change(input, { target: { files: [file] } });
    await fireEvent.click(screen.getByRole("button", { name: "Rückmeldung einholen" }));

    expect(onSubmitUploadFeedback).toHaveBeenCalledWith({
      taskId: "task-1",
      taskKind: "native",
      file,
      moduleId: null
    });
  });

  it("opens feedback first and nests qualitative criteria inside it", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-1",
            attempt_nr: 1,
            kind: "text",
            intent: "submit",
            created_at: "2026-04-05 10:00",
            analysis_status: "completed",
            text_body: "Meine Lösung",
            feedback_md: "## Rückmeldung\n\nGut gemacht.",
            analysis_json: {
              schema: "learning.v1",
              score: 8,
              text: "Stabil",
              criteria_results: [
                {
                  criterion: "Klarheit",
                  score: 8,
                  max_score: 10,
                  explanation_md: "Gut strukturiert."
                }
              ]
            }
          }
        ]
      }
    });

    await rerender({
      courseId: "course-1",
      task,
      taskTitle: "Aufgabe 5",
      unitType: "linear",
      expanded: true,
      reviewPanelOpen: true,
      history: [
        {
          id: "submission-1",
          attempt_nr: 1,
          kind: "text",
          intent: "submit",
          created_at: "2026-04-05 10:00",
          analysis_status: "completed",
          text_body: "Meine Lösung",
          feedback_md: "## Rückmeldung\n\nGut gemacht.",
          analysis_json: {
            schema: "learning.v1",
            score: 8,
            text: "Stabil",
            criteria_results: [
              {
                criterion: "Klarheit",
                score: 8,
                max_score: 10,
                explanation_md: "Gut strukturiert."
              }
            ]
          }
        }
      ]
    });

    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    const topLevelDisclosures = Array.from(
      responseGroup.querySelectorAll(".learning-response-group > .learning-response-panel > summary")
    );
    expect(topLevelDisclosures.map((item) => item.textContent?.trim())).toEqual(["Rückmeldung", "Meine Abgabe"]);
    expect(topLevelDisclosures[0]?.closest("details")).toHaveAttribute("open");
    expect(within(responseGroup).getByText("Meine Abgabe").closest("details")).not.toHaveAttribute("open");
    expect(within(responseGroup).getByText("Gut gemacht.")).toBeInTheDocument();

    await fireEvent.click(within(responseGroup).getByText("Kriterien im Detail"));
    expect(within(responseGroup).getByText("Klarheit")).toBeInTheDocument();
    const criteriaItem = within(responseGroup).getByText("Klarheit").closest("details");
    expect(criteriaItem?.textContent).toContain("Gelungen");
    expect(criteriaItem?.textContent).not.toContain("8/10");
    expect(within(responseGroup).getByText("Gut strukturiert.")).toBeInTheDocument();
  });

  it("focuses the active text editor when the learner continues from feedback", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: true,
        initialSubmissionMode: "text",
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-04-05 10:00",
            analysis_status: "completed",
            text_body: "Mein Entwurf",
            feedback_md: "Gut begonnen."
          }
        ]
      }
    });

    const editor = await screen.findByRole("textbox", { name: "text_body" });
    await fireEvent.click(screen.getByRole("button", { name: "Im Entwurf weiterarbeiten" }));
    expect(editor).toHaveFocus();
  });

  it("offers revision, final submission and the learning path after feedback", () => {
    const onReturnToLearningPath = vi.fn();
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        workspaceOnly: true,
        reviewPanelOpen: true,
        initialSubmissionMode: "text",
        onReturnToLearningPath,
        history: [
          {
            id: "11111111-1111-4111-8111-111111111111",
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-08-23T10:00:00Z",
            analysis_status: "completed",
            text_body: "Mein Entwurf",
            feedback_md: "Gut begonnen."
          }
        ]
      }
    });

    const actions = screen.getByRole("region", { name: "Dein nächster Schritt" });
    expect(within(actions).getByRole("button", { name: "Im Entwurf weiterarbeiten" })).toBeEnabled();
    expect(within(actions).getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
    expect(within(actions).getByRole("button", { name: "Zurück zum Lernpfad" })).toBeEnabled();
    expect(screen.getAllByRole("button", { name: "Endgültig abgeben" })).toHaveLength(1);
  });

  it("replaces editing actions with onward navigation after final submission", async () => {
    const onOpenNextTask = vi.fn();
    const onReturnToLearningPath = vi.fn();
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 1",
        unitType: "linear",
        workspaceOnly: true,
        reviewPanelOpen: true,
        nextTaskLabel: "Aufgabe 2",
        onOpenNextTask,
        onReturnToLearningPath,
        history: [
          {
            id: "22222222-2222-4222-8222-222222222222",
            attempt_nr: 2,
            kind: "text",
            intent: "submit",
            created_at: "2026-08-23T10:05:00Z",
            analysis_status: "completed",
            text_body: "Meine endgültige Fassung",
            feedback_md: "Gut abgeschlossen."
          }
        ]
      }
    });

    const actions = screen.getByRole("region", { name: "Aufgabe abgeschlossen" });
    expect(within(actions).queryByRole("button", { name: "Im Entwurf weiterarbeiten" })).toBeNull();
    expect(within(actions).queryByRole("button", { name: "Endgültig abgeben" })).toBeNull();

    await fireEvent.click(within(actions).getByRole("button", { name: "Weiter zu Aufgabe 2" }));
    expect(onOpenNextTask).toHaveBeenCalledOnce();
    await fireEvent.click(within(actions).getByRole("button", { name: "Zurück zum Lernpfad" }));
    expect(onReturnToLearningPath).toHaveBeenCalledOnce();
  });

  it("returns to the learning path when no later task is available", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Letzte Aufgabe",
        unitType: "linear",
        workspaceOnly: true,
        reviewPanelOpen: true,
        onReturnToLearningPath: vi.fn(),
        history: [
          {
            id: "33333333-3333-4333-8333-333333333333",
            attempt_nr: 2,
            kind: "text",
            intent: "submit",
            created_at: "2026-08-23T10:10:00Z",
            analysis_status: "completed",
            text_body: "Meine endgültige Fassung",
            feedback_md: "Gut abgeschlossen."
          }
        ]
      }
    });

    const actions = screen.getByRole("region", { name: "Aufgabe abgeschlossen" });
    expect(within(actions).queryByRole("button", { name: /^Weiter zu / })).toBeNull();
    expect(within(actions).getByRole("button", { name: "Zurück zum Lernpfad" })).toBeEnabled();
  });

  it("focuses the file field when the learner continues an upload from feedback", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: true,
        initialSubmissionMode: "upload",
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "image",
            intent: "feedback",
            created_at: "2026-04-05 10:00",
            analysis_status: "completed",
            feedback_md: "Gut begonnen."
          }
        ]
      }
    });

    const input = screen.getByLabelText("Datei auswählen");
    await fireEvent.click(screen.getByRole("button", { name: "Im Entwurf weiterarbeiten" }));
    expect(input).toHaveFocus();
  });

  it("places the response disclosures directly above the answer controls", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: true,
        history: [
          {
            id: "submission-1",
            attempt_nr: 1,
            kind: "text",
            intent: "submit",
            created_at: "2026-04-05 10:00",
            analysis_status: "completed",
            text_body: "Meine Lösung",
            feedback_md: "## Rückmeldung\n\nGut gemacht.",
            analysis_json: {
              schema: "learning.v1",
              score: 8,
              text: "Stabil",
              criteria_results: []
            }
          }
        ]
      }
    });

    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    const answerFormat = screen.getByRole("group", { name: "Antwortform" });

    expect(document.querySelector(".learning-task-cta-row")).toBeNull();
    expect(responseGroup.compareDocumentPosition(answerFormat) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("uses the same CTA pattern for H5P tasks without rendering a history block", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          kind: "h5p",
          h5p: { content_id: "content-1" }
        },
        taskTitle: "Interaktive Aufgabe",
        unitType: "linear",
        expanded: true
      }
    });

    expect(screen.getByRole("button", { name: "Interaktive Aufgabe beginnen" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Letzte Abgabe" })).toBeNull();
  });

  it("shows a local pending note inside the open editor while feedback is being generated", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 6",
        unitType: "linear",
        expanded: true,
        history: [
          {
            id: "submission-2",
            attempt_nr: 2,
            kind: "text",
            intent: "feedback",
            created_at: "2026-04-07T10:35:29+00:00",
            analysis_status: "pending",
            text_body: "Ich weiß es doch auch nicht :("
          }
        ],
        submissionFocused: true,
        reviewPanelOpen: true,
        feedbackPending: true,
        feedbackStatusMessage: "Rückmeldung wird erstellt ..."
      }
    });
    expect(screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pausieren" })).toBeNull();
    expect(screen.getByText("Entwurf wird ausgewertet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rückmeldung einholen" })).toBeDisabled();
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveClass("status-message--progress");
  });

  it("shows the first feedback pending state inside the open editor even without a review panel", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 6",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        feedbackPending: true,
        feedbackStatusMessage: "Rückmeldung wird erstellt ...",
        pendingIntent: "feedback"
      }
    });

    expect(screen.getByRole("status")).toHaveTextContent("Rückmeldung wird erstellt ...");
    expect(screen.getByRole("button", { name: "Pausieren" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Meine Abgabe" })).toBeNull();
  });

  it("changes a long-running feedback request to a warning without duplicating the message", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 6",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        feedbackPending: true,
        feedbackStatusMessage: "Die Rückmeldung dauert länger als üblich ...",
        pendingIntent: "feedback"
      }
    });

    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveClass("status-message--warning");
  });

  it("opens completed feedback inline after the pending state finishes", async () => {
    const reviewedSubmissionId = "123e4567-e89b-42d3-a456-426614174012";
    const onDismissFeedbackStatus = vi.fn();
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 6",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        feedbackPending: true,
        feedbackStatusMessage: "Rückmeldung wird erstellt ...",
        history: [
          {
            id: reviewedSubmissionId,
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-08-09T08:00:00+00:00",
            analysis_status: "pending"
          }
        ],
        onDismissFeedbackStatus
      }
    });

    await rerender({
      courseId: "course-1",
      task,
      taskTitle: "Aufgabe 6",
      unitType: "linear",
      expanded: true,
      submissionFocused: true,
      feedbackPending: false,
      message: "feedback",
      feedbackStatusMessage: "Rückmeldung ist bereit",
      history: [
        {
          id: reviewedSubmissionId,
          attempt_nr: 1,
          kind: "text",
          intent: "feedback",
          created_at: "2026-08-09T08:00:00+00:00",
          analysis_status: "completed",
          text_body: "Mein Entwurf",
          feedback_md: "Gut erklärt."
        }
      ],
      onDismissFeedbackStatus
    });

    expect(screen.getByRole("status")).toHaveClass("status-message--success");
    expect(screen.queryByRole("button", { name: "Rückmeldung ansehen" })).toBeNull();
    expect(screen.getByText("Rückmeldung").closest("details")).toHaveAttribute("open");
    const editor = document.querySelector('textarea[aria-label="text_body"]') as HTMLTextAreaElement;
    await waitFor(() => expect(editor.value).toBe("Mein Entwurf"));
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
    expect(document.querySelector<HTMLInputElement>('input[name="feedback_submission_id"]')?.value).toBe(
      reviewedSubmissionId
    );
    expect(document.querySelector<HTMLInputElement>('input[name="finalization_idempotency_key"]')?.value).toBe(
      `finalize-${reviewedSubmissionId}`
    );
  });

  it("keeps a processing failure visible as an alert", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 6",
        unitType: "linear",
        expanded: true,
        feedbackStatusMessage: "Die Rückmeldung konnte nicht erstellt werden."
      }
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Die Rückmeldung konnte nicht erstellt werden.");
  });

  it("shows a completed final submission as closed review state with a retry action", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 7",
        unitType: "linear",
        expanded: true,
        history: [
          {
            id: "submission-9",
            attempt_nr: 2,
            kind: "text",
            intent: "submit",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            text_body: "Finale Lösung",
            feedback_md: "## Rückmeldung\n\nPasst."
          }
        ]
      }
    });

    expect(screen.queryByRole("button", { name: "Pausieren" })).toBeNull();
    expect(screen.getByRole("button", { name: "Erneut bearbeiten" })).toBeInTheDocument();
    expect(screen.getByText("Final abgegeben am 2026-04-07T12:10:00+00:00")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Meine Abgabe" })).toBeNull();
  });

  it("restores an uploaded snapshot and treats a replacement file as not yet reviewed", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: { ...task, has_submission: true },
        taskTitle: "Aufgabe 10",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        initialSubmissionMode: "upload",
        history: [
          {
            id: validReviewedSubmissionId,
            attempt_nr: 1,
            kind: "image",
            intent: "feedback",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            feedback_md: "Die Skizze ist gut lesbar.",
            files: [{ mime: "image/png", size: 2048, url: "/uploads/test.png" }]
          }
        ]
      }
    });

    const input = screen.getByLabelText("Datei auswählen") as HTMLInputElement;
    expect(input.value).toBe("");
    expect(screen.getByRole("region", { name: "Bisherige Datei" })).toHaveTextContent("Aktuelle Datei");
    expect(screen.getByRole("button", { name: "Andere Datei auswählen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();

    await fireEvent.change(input, {
      target: { files: [new File(["replacement"], "neu.png", { type: "image/png" })] }
    });

    expect(screen.getByRole("region", { name: "Ausgewählte Datei" })).toHaveTextContent("neu.png");
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
    const responseGroup = screen.getByRole("region", { name: "Rückmeldung zu deiner Abgabe" });
    expect(within(responseGroup).getByRole("img", { name: "Abgabevorschau" })).toHaveAttribute("src", "/uploads/test.png");
  });

  it("renders an inline image preview for uploaded image submissions", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          has_submission: true
        },
        taskTitle: "Aufgabe 10",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-image",
            attempt_nr: 1,
            kind: "image",
            intent: "feedback",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            files: [{ mime: "image/png", size: 2048, url: "/uploads/test.png" }]
          }
        ]
      }
    });

    await rerender({
      courseId: "course-1",
      task: {
        ...task,
        has_submission: true
      },
      taskTitle: "Aufgabe 10",
      unitType: "linear",
      expanded: true,
      reviewPanelOpen: true,
      history: [
        {
          id: "submission-image",
          attempt_nr: 1,
          kind: "image",
          intent: "feedback",
          created_at: "2026-04-07T12:10:00+00:00",
          analysis_status: "completed",
          files: [{ mime: "image/png", size: 2048, url: "/uploads/test.png" }]
        }
      ]
    });

    expect(screen.getByRole("img", { name: "Abgabevorschau" })).toBeInTheDocument();
  });

  it("renders an inline PDF preview for uploaded PDF submissions", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          has_submission: true
        },
        taskTitle: "Aufgabe 11",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-pdf",
            attempt_nr: 1,
            kind: "file",
            intent: "feedback",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            files: [{ mime: "application/pdf", size: 4096, url: "/uploads/test.pdf" }]
          }
        ]
      }
    });

    await rerender({
      courseId: "course-1",
      task: {
        ...task,
        has_submission: true
      },
      taskTitle: "Aufgabe 11",
      unitType: "linear",
      expanded: true,
      reviewPanelOpen: true,
      history: [
        {
          id: "submission-pdf",
          attempt_nr: 1,
          kind: "file",
          intent: "feedback",
          created_at: "2026-04-07T12:10:00+00:00",
          analysis_status: "completed",
          files: [{ mime: "application/pdf", size: 4096, url: "/uploads/test.pdf" }]
        }
      ]
    });

    expect(document.querySelector(".learning-task-submission-summary__frame")).not.toBeNull();
  });

  it("renders makecode hex submissions as curated code plus a download action", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          kind: "calliope",
          has_submission: true
        },
        taskTitle: "Aufgabe 12",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-hex",
            attempt_nr: 1,
            kind: "file",
            intent: "submit",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            text_body:
              '# makecode.evidence.v1\n\n## Summary\n\n- files_count: 2\n\n## Files\n\n### file: "main.ts"\n```typescript\nlet count = 1\n```\n\n### file: "main.py"\n```python\nprint("hi")\n```',
            files: [
              {
                mime: "application/x.makecode.hex",
                size: 4096,
                url: "/uploads/test.hex",
                download_url: "/uploads/test.hex?download=1"
              }
            ]
          }
        ]
      }
    });

    await rerender({
      courseId: "course-1",
      task: {
        ...task,
        kind: "calliope",
        has_submission: true
      },
      taskTitle: "Aufgabe 12",
      unitType: "linear",
      expanded: true,
      reviewPanelOpen: true,
      history: [
        {
          id: "submission-hex",
          attempt_nr: 1,
          kind: "file",
          intent: "submit",
          created_at: "2026-04-07T12:10:00+00:00",
          analysis_status: "completed",
          text_body:
            '# makecode.evidence.v1\n\n## Summary\n\n- files_count: 2\n\n## Files\n\n### file: "main.ts"\n```typescript\nlet count = 1\n```\n\n### file: "main.py"\n```python\nprint("hi")\n```',
          files: [
            {
              mime: "application/x.makecode.hex",
              size: 4096,
              url: "/uploads/test.hex",
              download_url: "/uploads/test.hex?download=1"
            }
          ]
        }
      ]
    });

    expect(screen.getByText('print("hi")')).toBeInTheDocument();
    expect(screen.queryByText("makecode.evidence.v1")).toBeNull();
    expect(screen.queryByText("let count = 1")).toBeNull();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute(
      "href",
      "/uploads/test.hex?download=1"
    );
  });

  it("renders scratch sb3 submissions as a structure view plus a download action", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          kind: "scratch",
          has_submission: true
        },
        taskTitle: "Aufgabe 13",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-sb3",
            attempt_nr: 1,
            kind: "file",
            intent: "submit",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            text_body:
              "# scratch.evidence.v2\n\n## Summary\n- stage_present: true\n\n## Target Stage\n### Script 1\n- event_whenflagclicked\n- looks_say MESSAGE=\"Hallo\"",
            files: [
              {
                mime: "application/x.scratch.sb3",
                size: 8192,
                url: "/uploads/test.sb3",
                download_url: "/uploads/test.sb3?download=1"
              }
            ]
          }
        ]
      }
    });

    await rerender({
      courseId: "course-1",
      task: {
        ...task,
        kind: "scratch",
        has_submission: true
      },
      taskTitle: "Aufgabe 13",
      unitType: "linear",
      expanded: true,
      reviewPanelOpen: true,
      history: [
        {
          id: "submission-sb3",
          attempt_nr: 1,
          kind: "file",
          intent: "submit",
          created_at: "2026-04-07T12:10:00+00:00",
          analysis_status: "completed",
          text_body:
            "# scratch.evidence.v2\n\n## Summary\n- stage_present: true\n\n## Target Stage\n### Script 1\n- event_whenflagclicked\n- looks_say MESSAGE=\"Hallo\"",
          files: [
            {
              mime: "application/x.scratch.sb3",
              size: 8192,
              url: "/uploads/test.sb3",
              download_url: "/uploads/test.sb3?download=1"
            }
          ]
        }
      ]
    });

    expect(document.querySelector(".scratch-evidence")).not.toBeNull();
    expect(screen.queryByText("scratch.evidence.v2")).toBeNull();
    expect(screen.getByText("Target Stage")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute(
      "href",
      "/uploads/test.sb3?download=1"
    );
  });

  it("renders filius fls submissions as a structure view plus a download action", async () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          kind: "filius",
          has_submission: true
        },
        taskTitle: "Aufgabe 14",
        unitType: "linear",
        expanded: true,
        reviewPanelOpen: false,
        history: [
          {
            id: "submission-fls",
            attempt_nr: 1,
            kind: "file",
            intent: "submit",
            created_at: "2026-04-07T12:10:00+00:00",
            analysis_status: "completed",
            text_body:
              "# filius.evidence.v1\n\n## Project\n- filius_version: 1.15.1\n\n## Ground Frame\n- class: filius.software.dhcp.DHCPServer",
            files: [
              {
                mime: "application/x.filius.fls",
                size: 8192,
                url: "/uploads/test.fls",
                download_url: "/uploads/test.fls?download=1"
              }
            ]
          }
        ]
      }
    });

    await rerender({
      courseId: "course-1",
      task: {
        ...task,
        kind: "filius",
        has_submission: true
      },
      taskTitle: "Aufgabe 14",
      unitType: "linear",
      expanded: true,
      reviewPanelOpen: true,
      history: [
        {
          id: "submission-fls",
          attempt_nr: 1,
          kind: "file",
          intent: "submit",
          created_at: "2026-04-07T12:10:00+00:00",
          analysis_status: "completed",
          text_body:
            "# filius.evidence.v1\n\n## Project\n- filius_version: 1.15.1\n\n## Ground Frame\n- class: filius.software.dhcp.DHCPServer",
          files: [
            {
              mime: "application/x.filius.fls",
              size: 8192,
              url: "/uploads/test.fls",
              download_url: "/uploads/test.fls?download=1"
            }
          ]
        }
      ]
    });

    expect(document.querySelector(".filius-evidence")).not.toBeNull();
    expect(screen.queryByText("filius.evidence.v1")).toBeNull();
    expect(screen.getByText("Ground Frame")).toBeInTheDocument();
    expect(screen.getByText(/filius\.software\.dhcp\.DHCPServer/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute(
      "href",
      "/uploads/test.fls?download=1"
    );
  });

  it("uses theme tokens for the task prompt and summary areas instead of legacy intro panels", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const blockMatch = css.match(/\.learning-work-item--task \.markdown-prose\s*\{([^}]*)\}/);

    expect(blockMatch).not.toBeNull();
    const block = blockMatch?.[1] ?? "";

    expect(block).toMatch(/background:\s*var\(--color-bg-muted\);/);
    expect(block).toMatch(/border-left:\s*3px solid var\(--color-accent\);/);
    expect(block).not.toMatch(/background:\s*#f8f5ee;/);
    expect(css).toMatch(/\.learning-task-inline-response\s*\{/);
    expect(css).not.toMatch(/\.learning-work-item__start-card\s*\{/);
  });

  it("styles the inline response controls as square disclosures instead of tabs", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const blockMatch = css.match(/\.learning-response-panel\s*\{([^}]*)\}/);

    expect(blockMatch).not.toBeNull();

    const block = blockMatch?.[1] ?? "";
    expect(block).toMatch(/border-radius:\s*0;/);
    expect(block).toMatch(/box-shadow:\s*none;/);
    expect(css).not.toMatch(/\.learning-task-submission-summary__tabs/);
  });
});
