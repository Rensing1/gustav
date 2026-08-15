import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import PracticeStackSelector from "./PracticeStackSelector.svelte";

const stacks = [
  {
    course_id: "course-1",
    course_title: "Politik-Wirtschaft",
    unit_id: "unit-1",
    unit_title: "Europäische Union",
    practice_module_id: "module-1",
    module_title: "Gesetzgebungsverfahren der EU",
    task_count: 3,
    due_tasks_count: 1
  },
  {
    course_id: "course-2",
    course_title: "Informatik",
    unit_id: "unit-2",
    unit_title: "TDD",
    practice_module_id: "module-2",
    module_title: "Tests verstehen",
    task_count: 2,
    due_tasks_count: 0
  }
];

describe("PracticeStackSelector", () => {
  it("offers accessible cards and derives the start count from mode and selection", async () => {
    render(PracticeStackSelector, { props: { stacks, selectedStack: null, selectedMode: "due" } });

    const start = screen.getByRole("button", { name: "Aufgaben auswählen" });
    expect(start).toBeDisabled();

    await fireEvent.click(screen.getByRole("checkbox", { name: /Gesetzgebungsverfahren der EU/ }));
    expect(screen.getByRole("button", { name: "1 Aufgabe starten" })).toBeEnabled();

    await fireEvent.click(screen.getByRole("radio", { name: /Alle Aufgaben üben/ }));
    expect(screen.getByRole("button", { name: "3 Aufgaben starten" })).toBeEnabled();
  });

  it("explains an empty due selection instead of starting an empty session", async () => {
    render(PracticeStackSelector, { props: { stacks, selectedStack: null, selectedMode: "due" } });
    await fireEvent.click(screen.getByRole("checkbox", { name: /Tests verstehen/ }));

    expect(screen.getByText("Für diese Auswahl ist heute nichts fällig.")).toBeVisible();
    expect(screen.getByRole("button", { name: "0 Aufgaben starten" })).toBeDisabled();
  });

  it("keeps topics and session setup in separate responsive regions", () => {
    const { container } = render(PracticeStackSelector, {
      props: { stacks, selectedStack: null, selectedMode: "due" }
    });

    expect(container.querySelector(".practice-selection__topics")).toBeInTheDocument();
    expect(container.querySelector(".practice-selection__setup")).toBeInTheDocument();
    expect(container.querySelector(".practice-selection__setup .practice-mode-picker")).toBeInTheDocument();
    expect(container.querySelector(".practice-selection__setup .practice-selection__footer")).toBeInTheDocument();
  });
});
