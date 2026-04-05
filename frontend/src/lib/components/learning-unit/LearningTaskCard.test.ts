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
  it("shows the full task statement inside the focused workspace", () => {
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

    expect(screen.getAllByRole("heading", { name: "Begriffe definieren" }).length).toBe(2);
    expect(screen.getByRole("heading", { name: "Arbeitsauftrag" })).toBeInTheDocument();
    expect(screen.getByText("Erkläre den Zusammenhang.")).toBeInTheDocument();
    expect(screen.getByText("Datei auswählen")).toBeInTheDocument();
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
    expect(screen.queryByText("Modul Graphen")).toBeNull();
    expect(screen.queryByText("Aufgabe")).toBeNull();
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
    expect(screen.queryByText("Modul Graphen")).toBeNull();
    expect(screen.queryByText("Aufgabe")).toBeNull();
    expect(screen.getByText("Erkläre den Zusammenhang.")).toBeInTheDocument();
  });
});
