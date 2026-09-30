import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import Page from "./+page.svelte";
import { buildLearningUnitFlow } from "$lib/graph/learning-unit-flow";
import type { PageData } from "./$types";

vi.mock("$lib/graph/learning-unit-flow", () => ({ buildLearningUnitFlow: vi.fn() }));

afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

it("catches a failed graph build and renders the graph after retry", async () => {
  vi.stubGlobal("matchMedia", () => Object.assign(new EventTarget(), { matches: false }));
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  const unit = { id: "unit-graph", title: "Lernpfad", unit_type: "modular" as const };
  const data: PageData = {
    bootstrap: null, appSessionActive: true, theme: "light", workspaceLayout: "standard",
    breadcrumbs: [], hidePageHeading: true, pageTitle: "Lernpfad",
    user: { sub: "learner", name: "Lernende Person", role: "student", roles: ["student"] },
    courseId: "course-graph", courseTitle: "Testkurs", unitId: unit.id,
    units: [{ unit, position: 1 }], selectedUnit: { unit, position: 1 }, sections: [],
    graph: { unit, phases: [], modules: [], edges: [] }, activeModule: null,
    initialView: "overview", requestedTaskId: null, initialPanel: null,
    historyTaskId: null, history: [], historyLoadState: "not_loaded",
    submittedTaskId: null, message: null, submissionMode: null
  };
  const build = vi.mocked(buildLearningUnitFlow);
  build.mockRejectedValueOnce(new Error("layout_failed")).mockResolvedValue({
    nodes: [{ id: "module", type: "unitNode", position: { x: 0, y: 0 }, data: { kind: "module", title: "Grundlagen", kicker: "Modul", meta: "", openable: true } }],
    edges: []
  });
  render(Page, { props: { data, form: null } });
  await screen.findByText("Der Lernpfad konnte nicht aufgebaut werden. Bitte versuche es erneut.");
  expect(document.querySelector(".svelte-flow")).toBeNull();
  await fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
  await waitFor(() => expect(document.querySelector(".svelte-flow")).not.toBeNull());
  expect(screen.queryByRole("alert")).toBeNull();
  expect(build).toHaveBeenCalledTimes(2);
});
