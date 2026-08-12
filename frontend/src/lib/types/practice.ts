export type LearningPracticeStack = {
  course_id: string;
  course_title: string;
  unit_id: string;
  unit_title: string;
  practice_module_id: string;
  module_title: string;
  task_count: number;
  due_tasks_count: number;
};

export type LearningPracticeSessionItem = {
  id: string;
  course_id: string;
  practice_module_id: string;
  task_id: string;
  position: number;
  status: "active" | "awaiting_analysis" | "feedback" | "retry_queued";
  presentation_number: 1 | 2;
  kind: "native" | "h5p";
  instruction_md: string;
  criteria: string[];
  h5p_content_id: string | null;
  latest_attempt_id: string | null;
};

export type LearningPracticeSession = {
  id: string;
  mode: "due" | "exam";
  status: "active" | "ended";
  started_at: string;
  ended_at: string | null;
  total_items: number;
  completed_items: number;
  current_item: LearningPracticeSessionItem | null;
};

export type LearningPracticeAttempt = {
  id: string;
  status: "pending" | "completed" | "failed";
  classification: "secure" | "partial" | "insufficient" | null;
  fulfillment: number | null;
  feedback_md: string | null;
  due_at: string | null;
};
