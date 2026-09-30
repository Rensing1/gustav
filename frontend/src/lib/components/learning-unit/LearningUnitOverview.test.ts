import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import LearningUnitOverview from "./LearningUnitOverview.svelte";

afterEach(cleanup);

it("explains graph build failure and offers a retry instead of an empty canvas", async () => {
  const retry = vi.fn();
  const view = render(LearningUnitOverview, { props: { graph: null, nodes: [], edges: [], error: "Der Lernpfad konnte nicht aufgebaut werden.", onRetry: retry } });
  expect(screen.getByText("Der Lernpfad konnte nicht aufgebaut werden.")).toBeVisible();
  await fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
  expect(retry).toHaveBeenCalledOnce();
  await view.rerender({ graph: null, nodes: [], edges: [], error: null, busy: true, onRetry: retry });
  expect(screen.getByText("Lernpfad wird aufgebaut …")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Erneut versuchen" })).toBeNull();
  await view.rerender({ graph: null, nodes: [], edges: [], error: null, busy: false, onRetry: retry });
  expect(screen.getByText("Der Graph konnte nicht geladen werden.")).toBeVisible();
  await view.rerender({ graph: { unit: { id: "empty", title: "Leerer Lernpfad", unit_type: "modular" }, phases: [], modules: [], edges: [] }, nodes: [], edges: [], error: null, busy: false, onRetry: retry });
  expect(screen.getByText("Der Lernpfad enthält noch keine Module.")).toBeVisible();
  expect(document.querySelector(".svelte-flow")).toBeNull();
});
