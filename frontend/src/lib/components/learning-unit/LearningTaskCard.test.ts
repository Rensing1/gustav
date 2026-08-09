import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
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

const currentDir = path.dirname(fileURLToPath(import.meta.url));

describe("LearningTaskCard", () => {
  afterEach(() => {
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

    expect(window.sessionStorage.getItem(scopedKey)).toBe("Inline neu");
    expect(window.sessionStorage.getItem(legacyKey)).toBeNull();
    expect(window.localStorage.getItem(legacyKey)).toBeNull();
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

    expect(screen.getByText("## Arbeitsauftrag")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aufgabe 3 beginnen" })).toBeInTheDocument();
    expect(screen.queryByText("Aufgabe offen")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Aufgabe 3" })).toBeNull();
    expect(screen.queryByText(/Erkläre/i)).toBeNull();
    expect(document.querySelector(".learning-task-row")).not.toBeNull();
    expect(document.querySelector(".learning-task-row__copy")).not.toBeNull();
    expect(document.querySelector(".learning-task-row__preview")).not.toBeNull();
    expect(document.querySelector(".learning-task-row__actions")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Pausieren" })).toBeNull();
  });

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

    expect(screen.getByRole("button", { name: "Meine Abgabe" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entwurf weiterbearbeiten" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeInTheDocument();
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

    const { rerender } = render(LearningTaskCard, {
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
    expect(screen.getByRole("region", { name: "Meine Abgabe" })).toBeInTheDocument();
    expect(screen.getByText(/Erkläre/i, { exact: false })).toBeInTheDocument();

    await rerender({
      courseId: "course-1",
      task,
      taskTitle: "Aufgabe 3",
      unitType: "modular",
      compactLayout: true,
      expanded: true,
      submissionFocused: true,
      history
    });

    expect(document.querySelector(".learning-task-row")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Pausieren" })).toBeInTheDocument();
    expect(screen.queryByText("Die Bearbeitung bleibt Teil derselben Arbeitsfläche.")).toBeNull();
    expect(document.querySelector(".learning-task-inline-editor__statement")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Arbeitsauftrag" })).toBeInTheDocument();
    expect(screen.getByText(/Erkläre/i, { exact: false })).toBeInTheDocument();
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

    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose h2")).not.toBeNull();
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose strong")).not.toBeNull();
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose br")).not.toBeNull();
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose ol")).not.toBeNull();
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose table")).not.toBeNull();

    await fireEvent.click(screen.getByRole("tab", { name: "Rückmeldung" }));
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose em")).not.toBeNull();
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose ul")).not.toBeNull();

    await fireEvent.click(screen.getByRole("tab", { name: "Auswertung" }));
    expect(screen.getByRole("link", { name: "Hinweis" })).toHaveAttribute("href", "https://example.com");
    expect(document.querySelector(".learning-task-submission-summary__panel .markdown-prose table")).not.toBeNull();
  });

  it("keeps unloaded history from looking like missing feedback or evaluation", async () => {
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
        history: [],
        historyState: "loading"
      }
    });

    expect(screen.getByText("Die Abgabe wird geladen ...")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("tab", { name: "Rückmeldung" }));
    expect(screen.getByText("Die Abgabe wird geladen ...")).toBeInTheDocument();
    expect(screen.queryByText("Es liegt noch keine Rückmeldung vor.")).toBeNull();

    await fireEvent.click(screen.getByRole("tab", { name: "Auswertung" }));
    expect(screen.getByText("Die Abgabe wird geladen ...")).toBeInTheDocument();
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

  it("shows separate review and retry actions when a submission exists", async () => {
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
    expect(screen.getByRole("button", { name: "Meine Abgabe" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Erneut bearbeiten" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Meine Abgabe" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Weitere Versuche" })).toBeNull();
  });

  it("enables final submit only when the latest draft has completed feedback", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task: {
          ...task,
          has_submission: true,
          latest_submission_intent: "feedback",
          latest_submission_analysis_status: "completed",
          latest_submission_created_at: "2026-04-07T10:35:29+00:00"
        },
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        history: []
      }
    });

    expect(screen.getByText("Entwurf mit Rückmeldung vorhanden")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Meine Abgabe" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entwurf weiterbearbeiten" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
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
    expect(editor).toBeVisible();
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

  it("opens the review area with submission, feedback and evaluation views", async () => {
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

    const summary = screen.getByRole("region", { name: "Meine Abgabe" });
    const tabs = within(summary).getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent?.trim())).toEqual(["Abgabe", "Rückmeldung", "Auswertung"]);
    expect(within(summary).getByText("Meine Lösung")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("tab", { name: "Rückmeldung" }));
    expect(within(summary).getByText("Gut gemacht.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("tab", { name: "Auswertung" }));
    expect(within(summary).getByText("Klarheit")).toBeInTheDocument();
    const criteriaItem = within(summary).getByText("Klarheit").closest("li");
    expect(criteriaItem?.textContent).toContain("8/10");
    expect(within(summary).getByText("Gut strukturiert.")).toBeInTheDocument();
  });

  it("keeps the action row above the review area so the review toggle stays in place", () => {
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

    const actionRow = document.querySelector(".learning-task-cta-row");
    const summary = screen.getByRole("region", { name: "Meine Abgabe" });

    expect(actionRow).not.toBeNull();
    expect(actionRow && (actionRow.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING)).toBeTruthy();
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
    expect(screen.queryByRole("region", { name: "Meine Abgabe" })).toBeNull();
    expect(screen.getByRole("button", { name: "Pausieren" })).toBeInTheDocument();
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

  it("offers the completed feedback without opening it automatically", async () => {
    const onToggleReviewPanel = vi.fn();
    const onDismissFeedbackStatus = vi.fn();
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 6",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        message: "feedback",
        feedbackStatusMessage: "Rückmeldung ist bereit",
        history: [
          {
            id: "submission-ready",
            attempt_nr: 1,
            kind: "text",
            intent: "feedback",
            created_at: "2026-08-09T08:00:00+00:00",
            analysis_status: "completed",
            feedback_md: "Gut erklärt."
          }
        ],
        onToggleReviewPanel,
        onDismissFeedbackStatus
      }
    });

    expect(screen.getByRole("status")).toHaveClass("status-message--success");
    expect(screen.queryByRole("region", { name: "Meine Abgabe" })).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Rückmeldung ansehen" }));
    expect(onToggleReviewPanel).toHaveBeenCalledTimes(1);
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
    expect(screen.getByRole("button", { name: "Meine Abgabe" })).toBeInTheDocument();
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
    expect(css).toMatch(/\.learning-task-submission-summary\s*\{/);
    expect(css).not.toMatch(/\.learning-work-item__start-card\s*\{/);
  });

  it("styles the review tabs as technical text tabs instead of rounded pills", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const blockMatch = css.match(/\.learning-task-submission-summary__tabs \.workspace-tab\s*\{([^}]*)\}/);
    const activeBlockMatch = css.match(/\.learning-task-submission-summary__tabs \.workspace-tab--active\s*\{([^}]*)\}/);

    expect(blockMatch).not.toBeNull();
    expect(activeBlockMatch).not.toBeNull();

    const block = blockMatch?.[1] ?? "";
    const activeBlock = activeBlockMatch?.[1] ?? "";

    expect(block).toMatch(/border:\s*0;/);
    expect(block).toMatch(/border-bottom:\s*2px solid transparent;/);
    expect(block).toMatch(/border-radius:\s*0;/);
    expect(block).toMatch(/background:\s*transparent;/);
    expect(activeBlock).toMatch(/border-bottom-color:/);
    expect(activeBlock).toMatch(/background:\s*transparent;/);
    expect(activeBlock).toMatch(/box-shadow:\s*none;/);
  });
});
