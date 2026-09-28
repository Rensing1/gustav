import type {
  LivePracticeCell,
  LivePracticeModule,
  LiveSummaryCell,
  LiveSummaryPayload,
  LiveTask
} from "$lib/types/home";

export type LiveScoreTone = "empty" | "submitted" | "low" | "mid" | "high";

export type LiveLearningSummaryView = {
  completed: number;
  total: number;
  rated: number;
  average: number | null;
  averageLabel: string;
  tone: LiveScoreTone;
};

export type LiveLearningCellView = {
  task: LiveTask;
  cell: LiveSummaryCell;
  label: string;
  tone: LiveScoreTone;
};

export type LiveMatrixRowView = {
  student: { sub: string; name: string };
  learningCells: LiveLearningCellView[];
  learningSummary: LiveLearningSummaryView;
  practiceCells: Array<{ module: LivePracticeModule; cell: LivePracticeCell | null }>;
  practiceSummary: { due: number; secure: number };
};

export type LiveLearningGroupView = {
  id: string;
  title: string;
  taskIds: string[];
};

function formatScore(value: number): string {
  return new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(value);
}

function scoreTone(value: number): LiveScoreTone {
  if (value >= 8) return "high";
  if (value >= 4) return "mid";
  return "low";
}

function normalizedScore(task: LiveTask, cell: LiveSummaryCell): number | null {
  if (!cell.has_submission) return null;
  if (
    task.kind === "h5p" &&
    typeof cell.score_raw === "number" &&
    typeof cell.score_max === "number" &&
    cell.score_max > 0
  ) {
    return (cell.score_raw / cell.score_max) * 10;
  }
  return typeof cell.average_score === "number" ? cell.average_score : null;
}

function scorePresentation(task: LiveTask, cell: LiveSummaryCell): Pick<LiveLearningCellView, "label" | "tone"> {
  if (!cell.has_submission) {
    return { label: "–", tone: "empty" };
  }
  if (task.kind === "h5p" && typeof cell.score_raw === "number" && typeof cell.score_max === "number") {
    const normalized = cell.score_max > 0 ? (cell.score_raw / cell.score_max) * 10 : null;
    return {
      label: `${cell.score_raw}/${cell.score_max}`,
      tone: normalized === null ? "submitted" : scoreTone(normalized)
    };
  }
  if (typeof cell.average_score !== "number") {
    return { label: "•", tone: "submitted" };
  }
  return {
    label: formatScore(cell.average_score),
    tone: scoreTone(cell.average_score)
  };
}

function summarizeLearning(tasks: LiveTask[], cells: LiveSummaryCell[]): LiveLearningSummaryView {
  const scores = tasks.flatMap((task, index) => {
    const score = normalizedScore(task, cells[index]);
    return score === null ? [] : [score];
  });
  const average = scores.length > 0
    ? scores.reduce((sum, score) => sum + score, 0) / scores.length
    : null;

  return {
    completed: cells.filter((cell) => cell.has_submission).length,
    total: tasks.length,
    rated: scores.length,
    average,
    averageLabel: average === null ? "–" : formatScore(average),
    tone: average === null ? "empty" : scoreTone(average)
  };
}

/** Build presentation-only matrix groups and cells from the API read model. */
export function buildLiveMatrixView(summary: LiveSummaryPayload) {
  const learningTasks = summary.tasks.filter((task) => task.module_kind !== "practice");
  const learningGroups: LiveLearningGroupView[] = [];
  for (const task of learningTasks) {
    const id = task.section_id || task.module_id || "learning";
    const previous = learningGroups.at(-1);
    if (!previous || previous.id !== id) {
      learningGroups.push({
        id,
        title: task.section_title?.trim() || "Lernaufgaben",
        taskIds: [task.id]
      });
    } else {
      previous.taskIds.push(task.id);
    }
  }

  const rows: LiveMatrixRowView[] = summary.rows.map((row) => {
    const taskCells = new Map(row.tasks.map((cell) => [cell.task_id, cell]));
    const practiceCells = new Map(row.practice.map((cell) => [cell.module_id, cell]));
    const learningCells = learningTasks.map((task) => {
      const cell = taskCells.get(task.id) ?? { task_id: task.id, has_submission: false, average_score: null };
      return { task, cell, ...scorePresentation(task, cell) };
    });
    const orderedPracticeCells = summary.practice_modules.map((module) => ({
      module,
      cell: practiceCells.get(module.id) ?? null
    }));
    return {
      student: row.student,
      learningCells,
      learningSummary: summarizeLearning(learningTasks, learningCells.map((entry) => entry.cell)),
      practiceCells: orderedPracticeCells,
      practiceSummary: {
        due: row.practice.reduce((sum, cell) => sum + cell.due_tasks_count, 0),
        secure: row.practice.reduce((sum, cell) => sum + cell.secure_tasks_count, 0)
      }
    };
  });

  return { learningTasks, learningGroups, practiceModules: summary.practice_modules, rows };
}
