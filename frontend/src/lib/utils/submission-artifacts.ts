import { renderMarkdown } from "$lib/utils/markdown";
import type { LearningSubmission } from "$lib/types/learning";

type SubmissionFile = NonNullable<LearningSubmission["files"]>[number];

export type SubmissionArtifactView =
  | {
      kind: "makecode";
      code: string;
      filename: string;
      language: "python" | "typescript";
      downloadUrl: string | null;
      fileSummary: string;
    }
  | {
      kind: "scratch";
      html: string;
      downloadUrl: string | null;
      fileSummary: string;
    }
  | {
      kind: "filius";
      html: string;
      downloadUrl: string | null;
      fileSummary: string;
    };

function submissionFile(submission: LearningSubmission): SubmissionFile | null {
  return submission.files?.[0] ?? null;
}

function formatBytes(size: number | null | undefined): string {
  if (!size || size <= 0) {
    return "Datei";
  }
  if (size < 1024 * 1024) {
    return `${Math.max(1, Math.round(size / 1024))} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function submissionText(submission: LearningSubmission): string {
  const textBody = typeof submission.text_body === "string" ? submission.text_body.trim() : "";
  if (textBody) {
    return textBody;
  }
  const analysisText = typeof submission.analysis_json?.text === "string" ? submission.analysis_json.text.trim() : "";
  return analysisText;
}

function normalizeArtifactMarkdown(raw: string): string {
  return String(raw || "").replace(/^\uFEFF/u, "").trimStart();
}

function decodeFileName(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    return typeof parsed === "string" ? parsed : raw;
  } catch {
    return raw.trim();
  }
}

function parseMakecodeCode(markdown: string): { code: string; filename: string; language: "python" | "typescript" } | null {
  const normalized = normalizeArtifactMarkdown(markdown);
  if (!normalized.startsWith("# makecode.evidence.v1")) {
    return null;
  }

  const files = Array.from(normalized.matchAll(/^### file:\s+(.+)\r?\n(`{3,})([^\n]*)\r?\n([\s\S]*?)\r?\n\2$/gm)).map((match) => ({
    filename: decodeFileName(match[1] ?? ""),
    code: (match[4] ?? "").trimEnd()
  }));

  const preferred = files.find((entry) => entry.filename === "main.py") ?? files.find((entry) => entry.filename === "main.ts");
  if (!preferred || !preferred.code) {
    return null;
  }

  return {
    code: preferred.code,
    filename: preferred.filename,
    language: preferred.filename.endsWith(".py") ? "python" : "typescript"
  };
}

function renderScratchEvidence(markdown: string): string | null {
  const normalized = normalizeArtifactMarkdown(markdown);
  if (!normalized.startsWith("# scratch.evidence.v2")) {
    return null;
  }
  const withoutSchemaHeading = normalized.replace(/^# scratch\.evidence\.v2\s*\r?\n+/u, "");
  return renderMarkdown(withoutSchemaHeading);
}

function renderFiliusEvidence(markdown: string): string | null {
  const normalized = normalizeArtifactMarkdown(markdown);
  if (!normalized.startsWith("# filius.evidence.v1")) {
    return null;
  }
  const withoutSchemaHeading = normalized.replace(/^# filius\.evidence\.v1\s*\r?\n+/u, "");
  return renderMarkdown(withoutSchemaHeading);
}

export function buildSubmissionArtifactView(submission: LearningSubmission): SubmissionArtifactView | null {
  const file = submissionFile(submission);
  if (!file) {
    return null;
  }

  const downloadUrl = file.download_url ?? file.url ?? null;
  const fileSummary = `${file.mime} · ${formatBytes(file.size)}`;
  const markdown = submissionText(submission);

  if (file.mime === "application/x.makecode.hex") {
    const parsed = parseMakecodeCode(markdown);
    if (!parsed) {
      return null;
    }
    return {
      kind: "makecode",
      code: parsed.code,
      filename: parsed.filename,
      language: parsed.language,
      downloadUrl,
      fileSummary
    };
  }

  if (file.mime === "application/x.scratch.sb3") {
    const html = renderScratchEvidence(markdown);
    if (!html) {
      return null;
    }
    return {
      kind: "scratch",
      html,
      downloadUrl,
      fileSummary
    };
  }

  if (file.mime === "application/x.filius.fls") {
    const html = renderFiliusEvidence(markdown);
    if (!html) {
      return null;
    }
    return {
      kind: "filius",
      html,
      downloadUrl,
      fileSummary
    };
  }

  return null;
}
