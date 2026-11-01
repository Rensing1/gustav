export type DiagramResult =
  | { png: string; width: number; height: number }
  | { error: "invalid_diagram" | "diagram_too_large" };

/** Request private PNGs from the same renderer used by the PDF adapter. */
export async function renderDiagrams(sources: string[], theme: "light" | "dark", signal: AbortSignal): Promise<DiagramResult[]> {
  const response = await fetch("/api/markdown/diagrams", {
    method: "POST", credentials: "same-origin", cache: "no-store", signal,
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sources, theme })
  });
  if (!response.ok) throw new Error("diagram_renderer_unavailable");
  const { diagrams } = await response.json();
  if (!Array.isArray(diagrams) || diagrams.length !== sources.length || diagrams.some((item) =>
    !(item?.error === "invalid_diagram" || item?.error === "diagram_too_large" ||
      (typeof item?.png === "string" && Number.isFinite(item.width) && item.width > 0 && Number.isFinite(item.height) && item.height > 0)))) {
    throw new Error("invalid_diagram_results");
  }
  return diagrams;
}
