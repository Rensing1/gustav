import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import LearningTaskCard from "./LearningTaskCard.svelte";
const props = { courseId: "course", learnerSub: "learner", task: { id: "task", kind: "native" as const, instruction_md: "Antwort", criteria: [], h5p_completed: null, score_raw: null, score_max: null }, unitType: "linear" as const, submissionFocused: true };
afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); });

it("loads a server draft and confirms autosave without submitting for feedback", async () => {
  const request = vi.fn(async (_url, init) => Response.json({ text_body: init?.method === "PUT" ? JSON.parse(init.body).text_body : "Auf einem anderen Gerät geschrieben", updated_at: "now" }));
  vi.stubGlobal("fetch", request);
  render(LearningTaskCard, { props });
  const editor = screen.getByRole("textbox", { name: "Deine Antwort" });
  await waitFor(() => expect(editor).toHaveValue("Auf einem anderen Gerät geschrieben"));
  await fireEvent.input(editor, { target: { value: "Weitergeschrieben" } });
  await waitFor(() => expect(screen.getByText("Entwurf gespeichert – noch nicht abgegeben")).toBeVisible(), { timeout: 2500 });
  expect(request.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1);
});

it("keeps the editor open when pausing cannot save", async () => {
  vi.stubGlobal("fetch", vi.fn(async (_url, init) => new Response(null, { status: init?.method ? 503 : 204 })));
  const exit = vi.fn();
  render(LearningTaskCard, { props: { ...props, onExitSubmissionWorkspace: exit } });
  const editor = screen.getByRole("textbox", { name: "Deine Antwort" });
  await waitFor(() => expect(editor).toBeEnabled());
  await fireEvent.input(editor, { target: { value: "Nicht verlieren" } });
  await fireEvent.click(screen.getByRole("button", { name: "Pausieren" }));
  await screen.findByText(/Noch nicht auf dem Server gespeichert/);
  expect(exit).not.toHaveBeenCalled();
  expect(editor).toHaveValue("Nicht verlieren");
});

it("does not load drafts in previews or review panels", async () => {
  const request = vi.fn(); vi.stubGlobal("fetch", request);
  render(LearningTaskCard, { props: { ...props, submissionFocused: false, reviewPanelOpen: true } });
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(request).not.toHaveBeenCalled();
});
