import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import LearningTaskCard from "./LearningTaskCard.svelte";
import type { LearningTask } from "$lib/types/learning";

const task: LearningTask = {
  id: "task-1",
  instruction_md: "## Arbeitsauftrag\n\nErkläre den Zusammenhang.",
  criteria: ["Klarheit"],
  kind: "native"
};

describe("LearningTaskCard", () => {
  it("binds the inline markdown editor to local draft state instead of a constant empty string", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(path.resolve(currentDir, "LearningTaskCard.svelte"), "utf8");

    expect(source).toContain("let draftText = $state(\"\")");
    expect(source).toContain("function updateDraft(value: string)");
    expect(source).toContain("value={draftText}");
    expect(source).toContain("onInput={updateDraft}");
    expect(source).not.toContain("value=\"\"");
    expect(source).not.toContain("onInput={() => {}}");
  });

  it("opens inline editing controls inside the task flow instead of a separate workspace", () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Begriffe definieren",
        unitType: "linear",
        submissionFocused: true,
        initialSubmissionMode: "upload"
      }
    });

    expect(screen.getByRole("button", { name: "Bearbeitung schließen" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Arbeitsauftrag" })).toBeInTheDocument();
    expect(screen.getByText("Erkläre den Zusammenhang.")).toBeInTheDocument();
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

    const toggle = screen.getByRole("button", { name: /aufgabe 4/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Aufgabe 4");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).toBeNull();
    expect(screen.getByText("Modul Graphen")).toBeInTheDocument();
    expect(document.querySelector(".learning-work-item__kicker")).not.toBeNull();
    expect(screen.getByText("Erkläre den Zusammenhang.")).toBeInTheDocument();
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

    expect(screen.getByRole("button", { name: "Aufgabe bearbeiten" })).toBeInTheDocument();
    expect(screen.queryByText("Nächster Schritt")).toBeNull();
    expect(screen.queryByText("Antwortstatus")).toBeNull();
    expect(screen.queryByRole("tab", { name: "Abgabe" })).toBeNull();
  });

  it("shows the latest submission before a quieter retry CTA", async () => {
    render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 5",
        unitType: "linear",
        expanded: true,
        submitted: true,
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

    const summary = screen.getByRole("region", { name: "Letzte Abgabe" });
    const tabs = within(summary).getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent?.trim())).toEqual(["Abgabe", "Rückmeldung", "Auswertung"]);
    expect(within(summary).getByText("Meine Lösung")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Erneut bearbeiten" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Weitere Versuche" })).toBeInTheDocument();
    expect(screen.queryByText("Alter Versuch")).toBeNull();

    await fireEvent.click(screen.getByRole("tab", { name: "Rückmeldung" }));
    expect(within(summary).getByText("Gut gemacht.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("tab", { name: "Auswertung" }));
    expect(within(summary).getByText("Klarheit")).toBeInTheDocument();
    const criteriaItem = within(summary).getByText("Klarheit").closest("li");
    expect(criteriaItem?.textContent).toContain("8/10");
    expect(within(summary).getByText("Gut strukturiert.")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Weitere Versuche" }));
    expect(screen.getByText("Alter Versuch")).toBeInTheDocument();
    expect(screen.queryByText("Antwortstatus")).toBeNull();
    expect(screen.queryByText("Frühere Rückmeldung")).toBeNull();
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

    expect(screen.getByRole("button", { name: "Aufgabe bearbeiten" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Letzte Abgabe" })).toBeNull();
  });

  it("shows a local pending note while feedback is being generated", () => {
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
        feedbackPending: true,
        feedbackStatusMessage: "Rückmeldung wird erstellt ..."
      }
    });

    expect(screen.getByRole("region", { name: "Letzte Abgabe" })).toBeInTheDocument();
    expect(screen.getByText("Rückmeldung wird erstellt ...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rückmeldung einholen" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeDisabled();
  });

  it("keeps the editor open for feedback pending but closes it after a final pending submission", () => {
    const { rerender } = render(LearningTaskCard, {
      props: {
        courseId: "course-1",
        task,
        taskTitle: "Aufgabe 7",
        unitType: "linear",
        expanded: true,
        submissionFocused: true,
        feedbackPending: true,
        feedbackStatusMessage: "Rückmeldung wird erstellt ...",
        pendingIntent: "feedback"
      }
    });

    expect(screen.getByRole("button", { name: "Bearbeitung schließen" })).toBeInTheDocument();

    rerender({
      courseId: "course-1",
      task,
      taskTitle: "Aufgabe 7",
      unitType: "linear",
      expanded: true,
      submissionFocused: false,
      feedbackPending: true,
      feedbackStatusMessage: "Abgabe wird verarbeitet ...",
      pendingIntent: "submit"
    });

    expect(screen.queryByRole("button", { name: "Bearbeitung schließen" })).toBeNull();
    expect(screen.getByRole("button", { name: "Erneut bearbeiten" })).toBeInTheDocument();
  });

  it("uses theme tokens for the task prompt and summary areas instead of legacy intro panels", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/app.css"), "utf8");
    const blockMatch = css.match(/\.learning-work-item--task \.markdown-prose\s*\{([^}]*)\}/);

    expect(blockMatch).not.toBeNull();
    const block = blockMatch?.[1] ?? "";

    expect(block).toMatch(/background:\s*var\(--color-bg-muted\);/);
    expect(block).toMatch(/border-left:\s*3px solid var\(--color-accent\);/);
    expect(block).not.toMatch(/background:\s*#f8f5ee;/);
    expect(css).toMatch(/\.learning-task-submission-summary\s*\{/);
    expect(css).not.toMatch(/\.learning-work-item__start-card\s*\{/);
  });
});
