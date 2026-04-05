import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render, screen } from "@testing-library/svelte";
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

  it("shows a quiet start action and grouped response panels after submission", () => {
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
              criteria_results: []
            }
          }
        ]
      }
    });

    expect(screen.getByRole("button", { name: "Aufgabe bearbeiten" })).toBeInTheDocument();
    expect(screen.getByText("Abgabe")).toBeInTheDocument();
    expect(screen.getAllByText("Rückmeldung").length).toBeGreaterThan(0);
    expect(screen.getByText("Bewertung")).toBeInTheDocument();
    expect(screen.getByText("Antwortstatus")).toBeInTheDocument();
  });

  it("uses theme tokens for the task intro panel instead of a fixed light background", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/app.css"), "utf8");
    const blockMatch = css.match(/\.learning-work-item--task \.markdown-prose\s*\{([^}]*)\}/);

    expect(blockMatch).not.toBeNull();
    const block = blockMatch?.[1] ?? "";

    expect(block).toMatch(/background:\s*var\(--color-bg-muted\);/);
    expect(block).toMatch(/border-left:\s*3px solid var\(--color-accent\);/);
    expect(block).not.toMatch(/background:\s*#f8f5ee;/);
  });
});
