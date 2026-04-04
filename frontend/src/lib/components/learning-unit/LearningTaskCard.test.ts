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
});
