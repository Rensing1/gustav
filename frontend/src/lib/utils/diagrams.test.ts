import { afterEach, expect, it, vi } from "vitest";
import { renderDiagrams } from "./diagrams";

afterEach(() => vi.unstubAllGlobals());
it("sends one private same-origin batch with its theme and cancellation signal", async () => {
  const results = [{ png: "aGVsbG8=", width: 10, height: 20 }, { error: "invalid_diagram" }];
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ diagrams: results }) });
  vi.stubGlobal("fetch", fetch);
  const signal = new AbortController().signal;
  expect(await renderDiagrams(["first", "broken"], "dark", signal)).toEqual(results);
  expect(fetch).toHaveBeenCalledWith("/api/markdown/diagrams", expect.objectContaining({
    method: "POST", cache: "no-store", credentials: "same-origin", signal,
    body: JSON.stringify({ sources: ["first", "broken"], theme: "dark" })
  }));
});
it.each([null, [], [{ png: "x", width: 0, height: 1 }], [{ error: "private diagnostic" }]])(
  "rejects malformed responses", async (diagrams) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ diagrams }) }));
    await expect(renderDiagrams(["source"], "light", new AbortController().signal)).rejects.toThrow("invalid_diagram_results");
  }
);
it("reports transport failure without presenting server diagnostics", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  await expect(renderDiagrams(["source"], "light", new AbortController().signal)).rejects.toThrow("diagram_renderer_unavailable");
});
