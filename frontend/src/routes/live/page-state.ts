import type { LiveDetailSubmission, LiveSummaryPayload, LiveTask, LiveUnitDashboardView } from "$lib/types/home";

export type SortKey = "student" | "progress" | "average" | "latest";
export type SortDirection = "asc" | "desc";

export type LiveWorkspaceSelection = {
  courseId: string | null;
  unitId: string | null;
  studentSub: string | null;
  taskId: string | null;
};

type LiveWorkspaceResolvedSelection = {
  courseId: string;
  unitId: string;
  studentSub: string;
  taskId: string;
};

export type LiveWorkspaceControllerState = LiveWorkspaceSelection & {
  summary: LiveSummaryPayload | null;
  detail: LiveDetailSubmission | null;
  cursor: string | null;
  activeSortKey: SortKey | null;
  activeSortDirection: SortDirection | null;
};

type LiveDeltaCell = {
  student_sub?: string | null;
  task_id?: string | null;
  changed_at?: string | null;
};

type LiveDeltaResult =
  | { status: 204 }
  | {
      status: 200;
      cursor: string;
      cells: LiveDeltaCell[];
    };

type LiveWorkspaceControllerOptions = {
  initialSummary: LiveSummaryPayload | null;
  initialDetail: LiveDetailSubmission | null;
  initialSelection: LiveWorkspaceSelection;
  initialCursor: string | null;
  syncHref?: (href: string) => void;
  fetchSummary: (args: { courseId: string; unitId: string }) => Promise<LiveSummaryPayload>;
  fetchDetail: (selection: LiveWorkspaceResolvedSelection) => Promise<LiveDetailSubmission | null>;
  fetchDelta: (args: { courseId: string; unitId: string; cursor: string }) => Promise<LiveDeltaResult>;
};

type LiveWorkspaceFallbackNavigate = (href: string, options: {
  keepFocus: boolean;
  noScroll: boolean;
  replaceState: boolean;
}) => Promise<void>;

export function buildLivePageHref(selection: LiveWorkspaceSelection): string {
  const params = new URLSearchParams();
  if (selection.courseId) {
    params.set("course_id", selection.courseId);
  }
  if (selection.unitId) {
    params.set("unit_id", selection.unitId);
  }
  if (selection.studentSub) {
    params.set("student_sub", selection.studentSub);
  }
  if (selection.taskId) {
    params.set("task_id", selection.taskId);
  }
  return params.size ? `/live?${params.toString()}` : "/live";
}

export async function navigateWithLiveSelectionFallback(args: {
  href: string;
  trySelect: () => Promise<void>;
  goto: LiveWorkspaceFallbackNavigate;
}): Promise<"local" | "fallback"> {
  try {
    await args.trySelect();
    return "local";
  } catch {
    await args.goto(args.href, {
      keepFocus: true,
      noScroll: true,
      replaceState: true
    });
    return "fallback";
  }
}

export function buildLiveSummaryPath(selection: Pick<LiveWorkspaceSelection, "courseId" | "unitId">): string | null {
  if (!selection.courseId || !selection.unitId) {
    return null;
  }
  return `/live/courses/${encodeURIComponent(selection.courseId)}/units/${encodeURIComponent(selection.unitId)}/summary`;
}

export function buildLiveDetailSheetPath(selection: LiveWorkspaceResolvedSelection): string {
  const query = new URLSearchParams({
    student_sub: selection.studentSub,
    task_id: selection.taskId
  });
  return `/live/courses/${encodeURIComponent(selection.courseId)}/units/${encodeURIComponent(selection.unitId)}/detail-sheet?${query.toString()}`;
}

export function buildLiveDeltaPath(args: { courseId: string; unitId: string; cursor: string }): string {
  const query = new URLSearchParams({ updated_since: args.cursor });
  return `/live/courses/${encodeURIComponent(args.courseId)}/units/${encodeURIComponent(args.unitId)}/submissions/delta?${query.toString()}`;
}

function rowForStudent(summary: LiveSummaryPayload | null, studentSub: string | null) {
  if (!summary || !studentSub) {
    return null;
  }
  return summary.rows.find((row) => row.student.sub === studentSub) ?? null;
}

export function defaultTaskIdForStudent(summary: LiveSummaryPayload | null, studentSub: string | null): string | null {
  const row = rowForStudent(summary, studentSub);
  if (!row) {
    return null;
  }
  let latestTaskId: string | null = null;
  let latestCreatedAt = "";
  for (const cell of row.tasks) {
    if (!cell.has_submission) {
      continue;
    }
    const createdAt = String(cell.created_at ?? "");
    if (createdAt >= latestCreatedAt) {
      latestCreatedAt = createdAt;
      latestTaskId = cell.task_id;
    }
  }
  if (latestTaskId) {
    return latestTaskId;
  }
  return row.tasks[0]?.task_id ?? null;
}

export function normalizeLiveSelection(
  summary: LiveSummaryPayload | null,
  requested: LiveWorkspaceSelection
): LiveWorkspaceSelection {
  const row = rowForStudent(summary, requested.studentSub);
  if (!row) {
    return {
      ...requested,
      studentSub: null,
      taskId: null
    };
  }
  const taskIds = new Set(row.tasks.map((cell) => cell.task_id));
  const taskId = requested.taskId && taskIds.has(requested.taskId)
    ? requested.taskId
    : defaultTaskIdForStudent(summary, requested.studentSub);
  return {
    ...requested,
    studentSub: row.student.sub,
    taskId
  };
}

function taskMetaById(tasks: LiveTask[]) {
  return new Map(tasks.map((task) => [task.id, task]));
}

export function buildDashboardViewModel(args: {
  summary: LiveSummaryPayload | null;
  selection: Pick<LiveWorkspaceSelection, "courseId" | "unitId" | "studentSub" | "taskId">;
  detail: LiveDetailSubmission | null;
  course: { id: string; title: string; href: string };
  unit: { id: string; title: string; position: number; href: string };
  user: LiveUnitDashboardView["user"];
}): LiveUnitDashboardView | null {
  if (!args.summary) {
    return null;
  }
  const { summary, selection } = args;
  const taskMeta = taskMetaById(summary.tasks);
  let submittedCells = 0;
  let totalCells = 0;
  const averageScores: number[] = [];

  const rows = summary.rows.map((row) => {
    const studentHref = buildLivePageHref({
      courseId: selection.courseId,
      unitId: selection.unitId,
      studentSub: row.student.sub,
      taskId: null
    });
    totalCells += row.tasks.length;
    const submitted = row.tasks.filter((cell) => cell.has_submission);
    submittedCells += submitted.length;
    const rowAverageSource = row.tasks
      .map((cell) => cell.average_score)
      .filter((value): value is number => typeof value === "number");
    if (rowAverageSource.length) {
      averageScores.push(rowAverageSource.reduce((sum, value) => sum + value, 0) / rowAverageSource.length);
    }
    let latestTaskId = "";
    let latestCreatedAt = "";
    let latestAverageScore: number | null = null;
    for (const cell of row.tasks) {
      if (!cell.has_submission) {
        continue;
      }
      const createdAt = String(cell.created_at ?? "");
      if (createdAt >= latestCreatedAt) {
        latestCreatedAt = createdAt;
        latestTaskId = cell.task_id;
        latestAverageScore = typeof cell.average_score === "number" ? cell.average_score : null;
      }
    }
    const latestTask = latestTaskId ? taskMeta.get(latestTaskId) ?? null : null;
    return {
      student: {
        ...row.student,
        href: studentHref
      },
      progress_percent: row.tasks.length ? Math.round((submitted.length / row.tasks.length) * 100) : 0,
      average_score: rowAverageSource.length
        ? rowAverageSource.reduce((sum, value) => sum + value, 0) / rowAverageSource.length
        : null,
      latest_submission: latestTask && latestCreatedAt
        ? {
            task_id: latestTaskId,
            task_position: latestTask.position,
            task_label: `${latestTask.position}. Aufgabe`,
            created_at: latestCreatedAt,
            average_score: latestAverageScore
          }
        : null,
      href: studentHref
    };
  });

  const selectedRow = rowForStudent(summary, selection.studentSub);
  const normalizedSelection = normalizeLiveSelection(summary, selection);
  const selectedTaskId = selectedRow ? normalizedSelection.taskId : null;
  const latestTaskId = defaultTaskIdForStudent(summary, selection.studentSub);
  const selectedStudentPanel = selectedRow
    ? {
        student: {
          ...selectedRow.student,
          href: buildLivePageHref({
            courseId: selection.courseId,
            unitId: selection.unitId,
            studentSub: selectedRow.student.sub,
            taskId: null
          })
        },
        tasks: summary.tasks.map((task) => {
          const cell = selectedRow.tasks.find((entry) => entry.task_id === task.id);
          return {
            task_id: task.id,
            task_position: task.position,
            task_label: `${task.position}. Aufgabe`,
            has_submission: Boolean(cell?.has_submission),
            average_score: typeof cell?.average_score === "number" ? cell.average_score : null,
            is_latest_submission: task.id === latestTaskId,
            href: buildLivePageHref({
              courseId: selection.courseId,
              unitId: selection.unitId,
              studentSub: selectedRow.student.sub,
              taskId: task.id
            })
          };
        }),
        selected_task_id: selectedTaskId,
        selected_task_detail: args.detail
      }
    : null;

  return {
    user: args.user,
    course: args.course,
    unit: args.unit,
    summary: {
      learners_count: rows.length,
      tasks_count: summary.tasks.length,
      completion_rate_percent: totalCells ? Math.round((submittedCells / totalCells) * 100) : 0,
      average_score: averageScores.length
        ? averageScores.reduce((sum, value) => sum + value, 0) / averageScores.length
        : null
    },
    rows,
    selected_student_panel: selectedStudentPanel
  };
}

export function createLiveWorkspaceController(options: LiveWorkspaceControllerOptions) {
  const state: LiveWorkspaceControllerState = {
    summary: options.initialSummary,
    detail: options.initialDetail,
    courseId: options.initialSelection.courseId,
    unitId: options.initialSelection.unitId,
    studentSub: options.initialSelection.studentSub,
    taskId: options.initialSelection.taskId,
    cursor: options.initialCursor,
    activeSortKey: null,
    activeSortDirection: null
  };
  let requestToken = 0;

  function syncHref(): void {
    if (typeof options.syncHref === "function") {
      options.syncHref(buildLivePageHref(state));
    }
  }

  async function loadDetailForSelection(selection: LiveWorkspaceSelection, token: number): Promise<LiveDetailSubmission | null> {
    if (!selection.courseId || !selection.unitId || !selection.studentSub || !selection.taskId) {
      return null;
    }
    const detail = await options.fetchDetail({
      courseId: selection.courseId,
      unitId: selection.unitId,
      studentSub: selection.studentSub,
      taskId: selection.taskId
    });
    if (token !== requestToken) {
      return state.detail;
    }
    return detail;
  }

  async function applySelection(nextSelection: LiveWorkspaceSelection): Promise<LiveWorkspaceControllerState> {
    const normalized = normalizeLiveSelection(state.summary, nextSelection);
    const token = ++requestToken;
    const detail = await loadDetailForSelection(normalized, token);
    if (token !== requestToken) {
      return { ...state };
    }
    state.courseId = normalized.courseId;
    state.unitId = normalized.unitId;
    state.studentSub = normalized.studentSub;
    state.taskId = normalized.taskId;
    state.detail = detail;
    syncHref();
    return { ...state };
  }

  return {
    getState(): LiveWorkspaceControllerState {
      return { ...state };
    },
    resetFromServer(args: {
      summary: LiveSummaryPayload | null;
      detail: LiveDetailSubmission | null;
      selection: LiveWorkspaceSelection;
      cursor: string | null;
    }): LiveWorkspaceControllerState {
      state.summary = args.summary;
      state.detail = args.detail;
      state.courseId = args.selection.courseId;
      state.unitId = args.selection.unitId;
      state.studentSub = args.selection.studentSub;
      state.taskId = args.selection.taskId;
      state.cursor = args.cursor;
      return { ...state };
    },
    toggleSort(key: SortKey): LiveWorkspaceControllerState {
      if (state.activeSortKey !== key) {
        state.activeSortKey = key;
        state.activeSortDirection = "desc";
        return { ...state };
      }
      if (state.activeSortDirection === "desc") {
        state.activeSortDirection = "asc";
        return { ...state };
      }
      state.activeSortKey = null;
      state.activeSortDirection = null;
      return { ...state };
    },
    async selectStudent(studentSub: string): Promise<LiveWorkspaceControllerState> {
      return applySelection({
        courseId: state.courseId,
        unitId: state.unitId,
        studentSub,
        taskId: defaultTaskIdForStudent(state.summary, studentSub)
      });
    },
    async selectTask(taskId: string): Promise<LiveWorkspaceControllerState> {
      if (!state.studentSub) {
        return { ...state };
      }
      return applySelection({
        courseId: state.courseId,
        unitId: state.unitId,
        studentSub: state.studentSub,
        taskId
      });
    },
    async poll(): Promise<boolean> {
      if (!state.courseId || !state.unitId || !state.cursor) {
        return false;
      }
      const previousSelection = {
        courseId: state.courseId,
        unitId: state.unitId,
        studentSub: state.studentSub,
        taskId: state.taskId
      };
      const result = await options.fetchDelta({
        courseId: state.courseId,
        unitId: state.unitId,
        cursor: state.cursor
      });
      if (result.status !== 200) {
        return false;
      }
      const nextSummary = await options.fetchSummary({
        courseId: state.courseId,
        unitId: state.unitId
      });
      const nextCursor = result.cursor;
      const activeCellChanged = result.cells.some(
        (cell) => cell.student_sub === state.studentSub && cell.task_id === state.taskId
      );
      const normalized = normalizeLiveSelection(nextSummary, state);
      let nextDetail = state.detail;
      const selectionChanged = normalized.studentSub !== previousSelection.studentSub
        || normalized.taskId !== previousSelection.taskId;
      if ((activeCellChanged || selectionChanged) && state.courseId && state.unitId && normalized.studentSub && normalized.taskId) {
        const token = ++requestToken;
        const detail = await loadDetailForSelection({
          ...state,
          studentSub: normalized.studentSub,
          taskId: normalized.taskId
        }, token);
        if (token === requestToken) {
          nextDetail = detail;
        }
      } else if (selectionChanged) {
        nextDetail = null;
      }
      state.summary = nextSummary;
      state.cursor = nextCursor;
      state.studentSub = normalized.studentSub;
      state.taskId = normalized.taskId;
      state.detail = nextDetail;
      syncHref();
      return true;
    }
  };
}
