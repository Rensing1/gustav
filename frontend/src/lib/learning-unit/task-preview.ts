export type TaskInstructionPreview = {
  text: string;
  truncated: boolean;
};

function plainMarkdownLine(line: string): string {
  return line
    .replace(/<br\s*\/?\s*>/gi, " ")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s+/, "")
    .replace(/[*_~`]/g, "")
    .replace(/<[^>]+>/g, "")
    .replace(/^\|\s*|\s*\|$/g, "")
    .replace(/\s*\|\s*/g, " · ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Builds a readable two-line preview and records whether more instruction follows. */
export function taskInstructionPreview(markdown: string, fallback: string): TaskInstructionPreview {
  const sourceLines = markdown
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !/^\|?\s*:?-{3,}/.test(line));
  const lines = sourceLines.map(plainMarkdownLine).filter(Boolean);
  const text = lines.join(" ").replace(/\s+/g, " ").trim() || fallback;
  return {
    text,
    truncated: lines.length > 1 || text.length > 120
  };
}

/** Reports whether the browser's two-line clamp hides rendered instruction text. */
export function taskPreviewIsVisuallyClipped(scrollHeight: number, clientHeight: number): boolean {
  return clientHeight > 0 && scrollHeight > clientHeight;
}
