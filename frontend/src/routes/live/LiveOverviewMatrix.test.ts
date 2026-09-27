import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import type { LiveSummaryPayload } from "$lib/types/home";
import LiveOverviewMatrix from "./LiveOverviewMatrix.svelte";
import { buildLiveMatrixView } from "./live-matrix-view";

function props() {
  const summary: LiveSummaryPayload = {
    cursor: "2026-09-27T10:00:00Z",
    tasks: [{ id: "task", module_id: "learning", module_kind: "learning", section_id: "section", section_title: "Lernen", position: 1, instruction_md: "Erkläre", kind: "native" }],
    practice_modules: [{ id: "practice", section_id: "practice-section", title: "Wiederholen", task_ids: ["practice-task"] }],
    rows: [{ student: { sub: "student", name: "Langer synthetischer Schülername" }, tasks: [], practice: [{ module_id: "practice", status: "locked", task_count: 1, due_tasks_count: 0, secure_tasks_count: 0, partial_tasks_count: 0, insufficient_tasks_count: 0, latest_activity_at: null, next_due_at: null }] }]
  };
  return {
    view: buildLiveMatrixView(summary), activeView: "learning" as "learning" | "practice",
    selectedStudentSub: "student", selectedTaskId: null,
    mobileLearningGroupId: "section", mobilePracticeModuleId: "practice",
    onViewChange: vi.fn(), onMobileLearningGroupChange: vi.fn(), onMobilePracticeModuleChange: vi.fn(),
    onOpenStudent: vi.fn(), onOpenTask: vi.fn(), onOpenPracticeModule: vi.fn()
  };
}

describe("Live overview matrix", () => {
  it("shows an explicit empty roster without fabricated student values", () => {
    const handlers = props();
    handlers.view.rows = [];
    render(LiveOverviewMatrix, { props: handlers });
    expect(screen.getByText("Noch keine Schüler im Kurs.")).toBeInTheDocument();
  });

  it("opens an unsubmitted task and keeps native view and module controls accessible", async () => {
    const handlers = props();
    render(LiveOverviewMatrix, { props: handlers });
    const cell = screen.getByRole("button", { name: /Lernen, Aufgabe 1: –/ });
    expect(cell).not.toBeDisabled();
    await fireEvent.click(cell);
    expect(handlers.onOpenTask).toHaveBeenCalledWith("student", "task");
    await fireEvent.click(screen.getByRole("radio", { name: "Üben" }));
    expect(handlers.onViewChange).toHaveBeenCalledWith("practice");
    await fireEvent.change(screen.getByRole("combobox", { name: "Modul" }), { target: { value: "section" } });
    expect(handlers.onMobileLearningGroupChange).toHaveBeenCalledWith("section");
    expect(screen.queryByText(/bearbeitet/)).not.toBeInTheDocument();
  });

  it("labels locked practice explicitly without inventing due counts", async () => {
    const handlers = { ...props(), activeView: "practice" as const };
    render(LiveOverviewMatrix, { props: handlers });
    const cell = screen.getByRole("button", { name: /Übungsmodul Wiederholen: Gesperrt/ });
    expect(cell).toHaveTextContent("Gesperrt");
    expect(cell).not.toHaveTextContent("fällig");
    await fireEvent.click(cell);
    expect(handlers.onOpenPracticeModule).toHaveBeenCalledWith("student", "practice", "practice-task");
  });
});
