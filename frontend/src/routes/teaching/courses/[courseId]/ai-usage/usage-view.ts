type UsageStage = "ocr" | "analysis" | "feedback" | "initial_starters" | "reply";

export type ApiUsageBreakdownItem = {
  model: string;
  stage: UsageStage;
  modality: "text" | "visual";
  call_kind: "primary" | "repair" | "no_criteria" | "dialog_generation";
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  known_events: number;
  unknown_events: number;
};

export type UsageBreakdownItem = {
  model: string;
  stage: UsageStage;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

export type CourseUsageView = {
  course: {
    id: string;
    title: string;
    href: string;
  };
  totals: {
    input_tokens: number | null;
    output_tokens: number | null;
    total_tokens: number | null;
    known_events: number;
    unknown_events: number;
    breakdown: UsageBreakdownItem[];
  };
};

export type TeacherCourseAiUsageApiView = {
  course: CourseUsageView["course"] & Record<string, unknown>;
  totals: Omit<CourseUsageView["totals"], "breakdown"> & {
    breakdown: Array<ApiUsageBreakdownItem & Record<string, unknown>>;
  } & Record<string, unknown>;
} & Record<string, unknown>;

export function usageLoadErrorMessage(status: number): string {
  if (status === 422) {
    return "Der gewählte Zeitraum ist ungültig.";
  }
  return "Die KI-Nutzung konnte nicht geladen werden. Bitte versuche es erneut.";
}

function visibleBreakdown(items: ApiUsageBreakdownItem[]): UsageBreakdownItem[] {
  const grouped = new Map<string, UsageBreakdownItem>();
  for (const item of items) {
    const key = JSON.stringify([item.model, item.stage]);
    const visibleItem = grouped.get(key) ?? {
      model: item.model,
      stage: item.stage,
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0
    };
    visibleItem.input_tokens += item.input_tokens ?? 0;
    visibleItem.output_tokens += item.output_tokens ?? 0;
    visibleItem.total_tokens += item.total_tokens ?? 0;
    grouped.set(key, visibleItem);
  }
  return [...grouped.values()];
}

/** Keep and merge only the dimensions that the teacher table makes visible. */
export function courseUsageForBrowser(apiView: TeacherCourseAiUsageApiView): CourseUsageView {
  return {
    course: {
      id: apiView.course.id,
      title: apiView.course.title,
      href: apiView.course.href
    },
    totals: {
      input_tokens: apiView.totals.input_tokens,
      output_tokens: apiView.totals.output_tokens,
      total_tokens: apiView.totals.total_tokens,
      known_events: apiView.totals.known_events,
      unknown_events: apiView.totals.unknown_events,
      breakdown: visibleBreakdown(apiView.totals.breakdown)
    }
  };
}
