import { cleanup, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const mock = vi.hoisted(() => ({ render: vi.fn() }));
vi.mock("$lib/utils/diagrams", () => ({ renderDiagrams: mock.render }));
import MarkdownContent from "./MarkdownContent.svelte";

afterEach(cleanup);
beforeEach(() => mock.render.mockReset().mockResolvedValue([{ png: "aGVsbG8=", width: 100, height: 50 }]));

it("requests a batch of explicitly marked blocks and displays ordinary images", async () => {
  const source = '```mermaid\nsequenceDiagram\nA->>B: Hallo\n```\n\n```text\nsequenceDiagram\n```';
  const { container } = render(MarkdownContent, { source });
  await waitFor(() => expect(container.querySelector("img")).not.toBeNull());
  expect(mock.render).toHaveBeenCalledWith(["sequenceDiagram\nA->>B: Hallo\n"], "light", expect.any(AbortSignal));
  expect(container.querySelector("details pre")?.textContent).toContain("A->>B: Hallo");
  expect(container.querySelector("code.language-text")?.textContent).toBe("sequenceDiagram\n");
});

it("keeps syntax and transport failures local and source readable", async () => {
  mock.render.mockResolvedValueOnce([{ error: "invalid_diagram" }]);
  const { container } = render(MarkdownContent, { source: 'Vorher\n\n```mermaid\nbroken\n```\n\nNachher' });
  await waitFor(() => expect(container.textContent).toContain("Das Diagramm konnte nicht dargestellt werden."));
  expect(container.textContent).toContain("broken");
  expect(container.textContent).toContain("Nachher");
});

it("aborts stale source/theme requests and ignores late answers after unmounting", async () => {
  let resolve: (value: unknown) => void = () => {};
  mock.render.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const view = render(MarkdownContent, { source: '```mermaid\nold\n```', theme: "light" });
  await waitFor(() => expect(mock.render).toHaveBeenCalledTimes(1));
  const signal = mock.render.mock.calls[0][2] as AbortSignal;
  await view.rerender({ source: '```mermaid\nnew\n```', theme: "dark" });
  await waitFor(() => expect(view.container.querySelector("img")).not.toBeNull());
  expect(signal.aborted).toBe(true);
  expect(mock.render.mock.calls[1][1]).toBe("dark");
  resolve([{ png: "STALE", width: 1, height: 1 }]);
  await Promise.resolve();
  expect(view.container.innerHTML).not.toContain("STALE");
  view.unmount();
  expect((mock.render.mock.calls[1][2] as AbortSignal).aborted).toBe(true);
});

it("does not contact the renderer for ordinary Markdown and renders nested diagrams declaratively", async () => {
  const plain = render(MarkdownContent, { source: "Text `<script>`" });
  expect(mock.render).not.toHaveBeenCalled();
  plain.unmount();
  const view = render(MarkdownContent, { source: '- Text\n\n  ```mermaid\n  flowchart LR\n  A-->B\n  ```' });
  await waitFor(() => expect(view.container.querySelector("li figure img")).not.toBeNull());
});

it("distinguishes a technical failure from invalid source", async () => {
  mock.render.mockRejectedValueOnce(new Error("private diagnostic"));
  const { container } = render(MarkdownContent, { source: "```mermaid\nsequenceDiagram\n```" });
  await waitFor(() => expect(container.textContent).toContain("Der Diagrammdienst ist vorübergehend nicht verfügbar."));
  expect(container.textContent).not.toContain("private diagnostic");
  expect(container.querySelector("details")?.open).toBe(true);
});
