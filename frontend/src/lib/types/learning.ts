import type { SessionBootstrapUser } from "$lib/types/session-bootstrap";

export type LearningCourseUnit = {
  unit: {
    id: string;
    title: string;
    summary?: string | null;
    unit_type: "linear" | "modular";
  };
  position: number;
};

export type LearningMaterial = {
  id: string;
  title: string;
  kind: "markdown" | "file";
  body_md?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  filename_original?: string | null;
  alt_text?: string | null;
  position?: number | null;
};

export type LearningTask = {
  id: string;
  instruction_md: string;
  criteria: string[];
  has_submission?: boolean;
  position?: number | null;
  kind: "native" | "h5p" | "visual" | "scratch" | "calliope";
  h5p?: {
    content_id?: string | null;
  } | null;
  max_attempts?: number | null;
};

export type LearningSection = {
  section: {
    id: string;
    title: string;
    position: number;
    unit_id: string;
  };
  materials: LearningMaterial[];
  tasks: LearningTask[];
};

export type LearningSubmission = {
  intent: "feedback" | "submit";
  files?: Array<{
    mime: string;
    size: number;
    url: string;
  }>;
  id: string;
  attempt_nr: number;
  kind: "text" | "image" | "file" | "h5p";
  created_at: string;
  analysis_status: "pending" | "extracted" | "completed" | "failed";
  text_body?: string | null;
  mime_type?: string | null;
  score_raw?: number | null;
  score_max?: number | null;
  feedback_md?: string | null;
  analysis_json?: {
    schema: string;
    score?: number | null;
    text?: string | null;
    criteria_results?: Array<{
      criterion: string;
      score?: number | null;
      max_score?: number | null;
      explanation_md?: string | null;
    }>;
  } | null;
};

export type LearningUnitGraphPhase = {
  id: string;
  title: string;
  position: number;
};

export type LearningUnitGraphModule = {
  id: string;
  title: string;
  phase_id: string;
  position_in_phase: number;
  required_prereq_count: number;
  prereq_done: number;
  prereq_required: number;
  tasks_done: number;
  tasks_total: number;
  materials_count: number;
  status: "locked" | "open" | "done";
};

export type LearningUnitGraph = {
  unit: {
    id: string;
    title: string;
    unit_type: "linear" | "modular";
  };
  phases: LearningUnitGraphPhase[];
  modules: LearningUnitGraphModule[];
  edges: Array<{ from: string; to: string }>;
};

export type LearningModuleContent = {
  module: {
    id: string;
    title: string;
    unit_id: string;
    phase_id: string;
    position_in_phase: number;
  };
  materials: LearningMaterial[];
  tasks: LearningTask[];
};

export type LearningCoursePageData = {
  user: SessionBootstrapUser | null;
  courseId: string;
  courseTitle: string;
  units: LearningCourseUnit[];
};

export type LearningUnitPageData = {
  user: SessionBootstrapUser | null;
  courseId: string;
  courseTitle: string;
  unitId: string;
  units: LearningCourseUnit[];
  selectedUnit: LearningCourseUnit | null;
  sections: LearningSection[];
  graph: LearningUnitGraph | null;
  activeModule: LearningModuleContent | null;
  historyTaskId: string | null;
  history: LearningSubmission[];
  submittedTaskId: string | null;
  message: string | null;
  submissionMode: "text" | "upload" | null;
};
