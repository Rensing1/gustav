import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { LiveStudentPanelTask } from "$lib/types/home";
import LiveTaskStrip from "./LiveTaskStrip.svelte";

const tasks: LiveStudentPanelTask[] = Array.from({ length: 13 }, (_, index) => ({
  task_id: `task-${index}`, task_position: 1, section_id: `module-${index}`,
  section_title: `Modul ${index + 1}`, task_label: `Modul ${index + 1} · Aufgabe 1`,
  has_submission: index > 0, average_score: index === 1 ? null : index > 1 ? 8 : null,
  is_latest_submission: index === 12, href: `/live?task_id=task-${index}`
}));

describe("compact Live task strip", () => {
  afterEach(cleanup);
  it("keeps order, accessible labels, selection and latest marking without visible button text", () => {
    render(LiveTaskStrip, { tasks, selectedTaskId: "task-0", onOpen: vi.fn() });
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(13);
    expect(links.map((link) => link.getAttribute("href"))).toEqual(tasks.map((task) => task.href));
    expect(links.every((link) => link.textContent?.trim() === "")).toBe(true);
    expect(links[0]).toHaveAttribute("aria-current", "true");
    expect(links[12]).toHaveClass("is-latest");
    expect(screen.getByText("Modul 1 · Aufgabe 1: Noch offen")).toBeInTheDocument();
  });
  it("prioritizes focus over hover and returns to selection without changing it", async () => {
    const onOpen = vi.fn((_taskId: string, event: MouseEvent) => event.preventDefault());
    render(LiveTaskStrip, { tasks, selectedTaskId: "task-0", onOpen });
    const links = screen.getAllByRole("link");
    await fireEvent.mouseEnter(links[1]);
    expect(screen.getByText("Modul 2 · Aufgabe 1: Noch unbewertet")).toBeInTheDocument();
    vi.spyOn(links[12], "matches").mockReturnValue(true);
    await fireEvent.focus(links[12]);
    expect(screen.getByText("Modul 13 · Aufgabe 1: Ø 8.0")).toBeInTheDocument();
    await fireEvent.blur(links[12]);
    expect(screen.getByText("Modul 2 · Aufgabe 1: Noch unbewertet")).toBeInTheDocument();
    await fireEvent.mouseLeave(links[1]);
    expect(screen.getByText("Modul 1 · Aufgabe 1: Noch offen")).toBeInTheDocument();
    await fireEvent.click(links[12]);
    expect(onOpen).toHaveBeenCalledWith("task-12", expect.any(MouseEvent));
  });
  it("does not let mouse focus pin the caption against later hover", async () => {
    render(LiveTaskStrip, { tasks, selectedTaskId: "task-0", onOpen: vi.fn() });
    const links = screen.getAllByRole("link");
    vi.spyOn(links[0], "matches").mockReturnValue(false);
    await fireEvent.focus(links[0]);
    await fireEvent.mouseEnter(links[12]);
    expect(screen.getByText("Modul 13 · Aufgabe 1: Ø 8.0")).toBeInTheDocument();
  });
  it("handles no tasks without inventing a selection", () => {
    render(LiveTaskStrip, { tasks: [], selectedTaskId: null, onOpen: vi.fn() });
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByText("Keine Aufgaben vorhanden.")).toBeInTheDocument();
  });
  it.each([[null, "submitted-unscored"], [0, "score-zero"], [3, "score-low"], [4, "score-mid"], [7, "score-mid"], [8, "score-high"], [10, "score-high"]] as const)("retains the existing score threshold for %s", (score, expected) => {
    render(LiveTaskStrip, { tasks: [{ ...tasks[0], has_submission: true, average_score: score }], selectedTaskId: "task-0", onOpen: vi.fn() });
    expect(screen.getByRole("link")).toHaveClass(`live-task-strip__item--${expected}`);
  });
  it("refreshes the selected caption when new live data arrives", async () => {
    const onOpen = vi.fn();
    const { rerender } = render(LiveTaskStrip, { tasks, selectedTaskId: "task-0", onOpen });
    await rerender({ tasks: [{ ...tasks[0], has_submission: true, average_score: 8 }], selectedTaskId: "task-0", onOpen });
    expect(screen.getByText("Modul 1 · Aufgabe 1: Ø 8.0")).toBeInTheDocument();
  });
});
