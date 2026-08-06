import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import LearningDialogWorkspace from "./LearningDialogWorkspace.svelte";
import type { LearningTask } from "$lib/types/learning";
import { readWorkspaceCssBundle } from "$lib/styles/test-css-bundle";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

const dialogTask: LearningTask = {
  id: "task-dialog",
  instruction_md: "Untersuche die Quelle im Gespräch.",
  criteria: [],
  kind: "dialog",
  dialog: {
    partner_name: "Archivarin",
    partner_description_md: "Eine sachkundige Gesprächspartnerin.",
    opening_message_md: "Was fällt dir an der Quelle auf?",
    response_mode: "free_text",
    max_rounds: 3,
    closing_prompt_md: "Fasse deine wichtigste Erkenntnis zusammen."
  }
};

type TestSession = {
  id: string;
  status: "active" | "completed" | "abandoned";
  round_count: number;
  dialog: NonNullable<LearningTask["dialog"]>;
  closing_answer_md: string | null;
  initial_sentence_starters: string[];
  initial_starters_status: "not_required" | "pending" | "generating" | "completed" | "failed";
  initial_generation_attempts: number;
  turns: Array<{
    id: string;
    round_nr: number;
    student_message_md: string;
    used_sentence_starter_md: string | null;
    used_sentence_starter_source: string | null;
    status: "generating" | "completed" | "failed";
    assistant_reply_md: string | null;
    sentence_starters: string[];
    generation_attempts: number;
  }>;
};

function session(overrides: Partial<TestSession> = {}): TestSession {
  return {
    id: "session-1",
    status: "active",
    round_count: 0,
    dialog: dialogTask.dialog!,
    closing_answer_md: null,
    initial_sentence_starters: [],
    initial_starters_status: "not_required",
    initial_generation_attempts: 0,
    turns: [],
    ...overrides
  };
}

function answeredSession(overrides: Partial<TestSession> = {}): TestSession {
  return session({
    round_count: 1,
    turns: [
      {
        id: "turn-1",
        round_nr: 1,
        student_message_md: "Die Quelle wirkt einseitig.",
        used_sentence_starter_md: null,
        used_sentence_starter_source: null,
        status: "completed",
        assistant_reply_md: "Woran erkennst du diese Einseitigkeit?",
        sentence_starters: [],
        generation_attempts: 1
      }
    ],
    ...overrides
  });
}

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
}

function renderDialog(current: TestSession, task: LearningTask = dialogTask, learnerSub: string | null = "student-1") {
  const fetchMock = vi.fn(async () => jsonResponse({ session: current }));
  vi.stubGlobal("fetch", fetchMock);
  render(LearningDialogWorkspace, {
    props: {
      learnerSub,
      courseId: "course-1",
      task
    }
  });
  return fetchMock;
}

describe("LearningDialogWorkspace", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("hides completion controls before the first answered turn", async () => {
    renderDialog(session());

    expect(await screen.findByText("Archivarin")).toBeInTheDocument();
    const partnerContext = screen.getByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
    const composer = screen.getByRole("region", { name: "Dialog fortsetzen" });
    expect(screen.getByLabelText("Deine Antwort (0/3)")).toBeInTheDocument();
    expect(screen.queryByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(partnerContext).getByRole("link", { name: "Pausieren" })).toBeInTheDocument();
    expect(within(partnerContext).getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeInTheDocument();
    expect(within(partnerContext).queryByRole("button", { name: "Antwort senden" })).toBeNull();
    expect(within(composer).getByRole("button", { name: "Antwort senden" })).toBeInTheDocument();
    expect(within(composer).queryByRole("link", { name: "Pausieren" })).toBeNull();
  });

  it("offers a deliberate transition while keeping the closing prompt hidden", async () => {
    renderDialog(answeredSession());

    const partnerContext = await screen.findByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
    const composer = screen.getByRole("region", { name: "Dialog fortsetzen" });
    expect(within(partnerContext).getByRole("button", { name: "Dialog beenden" })).toBeInTheDocument();
    expect(within(partnerContext).getByRole("link", { name: "Pausieren" })).toBeInTheDocument();
    expect(within(composer).getByRole("button", { name: "Antwort senden" })).toBeInTheDocument();
    expect(within(composer).queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(screen.queryByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeNull();
    expect(screen.getByLabelText("Deine Antwort (1/3)")).toBeInTheDocument();
  });

  it("opens and leaves the closing phase without a server mutation", async () => {
    const fetchMock = renderDialog(answeredSession());
    const endButton = await screen.findByRole("button", { name: "Dialog beenden" });

    await fireEvent.click(endButton);

    const partnerContext = screen.getByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
    const closing = screen.getByRole("region", { name: "Abschluss vorbereiten" });
    expect(screen.getByLabelText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeInTheDocument();
    expect(within(partnerContext).getByRole("link", { name: "Pausieren" })).toBeInTheDocument();
    expect(within(partnerContext).queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(closing).getByRole("button", { name: "Endgültig abgeben" })).toBeInTheDocument();
    expect(within(closing).getByRole("button", { name: "Zurück zum Dialog" })).toBeInTheDocument();
    expect(within(closing).queryByRole("link", { name: "Pausieren" })).toBeNull();
    expect(screen.queryByLabelText("Deine Antwort (1/3)")).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: "Zurück zum Dialog" }));

    expect(screen.getByLabelText("Deine Antwort (1/3)")).toBeInTheDocument();
    expect(screen.queryByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("restores a scoped closing phase and draft for the same learner session", async () => {
    const storageKey = "gustav.learning.dialog-closing-draft:student-1:course-1:task-dialog:session-1";
    window.sessionStorage.setItem(
      storageKey,
      JSON.stringify({ phase: "closing", closingAnswer: "Meine gespeicherte Erkenntnis" })
    );

    renderDialog(answeredSession());

    const closingField = await screen.findByLabelText("Fasse deine wichtigste Erkenntnis zusammen.");
    expect(closingField).toHaveValue("Meine gespeicherte Erkenntnis");

    await fireEvent.input(closingField, { target: { value: "Überarbeitete Erkenntnis" } });
    expect(JSON.parse(window.sessionStorage.getItem(storageKey) ?? "{}")).toEqual({
      phase: "closing",
      closingAnswer: "Überarbeitete Erkenntnis"
    });
  });

  it("does not restore another learner's closing draft and stores nothing without a learner", async () => {
    window.sessionStorage.setItem(
      "gustav.learning.dialog-closing-draft:student-2:course-1:task-dialog:session-1",
      JSON.stringify({ phase: "closing", closingAnswer: "Fremder Entwurf" })
    );

    renderDialog(answeredSession(), dialogTask, null);

    expect(await screen.findByRole("button", { name: "Dialog beenden" })).toBeInTheDocument();
    expect(screen.queryByText("Fremder Entwurf")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Dialog beenden" }));
    await fireEvent.input(screen.getByLabelText("Fasse deine wichtigste Erkenntnis zusammen."), {
      target: { value: "Nicht speichern" }
    });
    expect(window.sessionStorage.length).toBe(1);
  });

  it("uses the same two-step submission when no closing prompt exists", async () => {
    const taskWithoutPrompt: LearningTask = {
      ...dialogTask,
      dialog: { ...dialogTask.dialog!, closing_prompt_md: null }
    };
    renderDialog(
      answeredSession({ dialog: taskWithoutPrompt.dialog! }),
      taskWithoutPrompt
    );

    await fireEvent.click(await screen.findByRole("button", { name: "Dialog beenden" }));

    expect(screen.getByText("Mit der Abgabe wird der Dialog endgültig abgeschlossen und ein Versuch verbraucht.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /erkenntnis/i })).toBeNull();
    expect(screen.getByRole("button", { name: "Endgültig abgeben" })).toBeEnabled();
  });

  it("keeps the final round as an explicit transition without another answer field", async () => {
    renderDialog(answeredSession({ round_count: 3 }));

    expect(await screen.findByText("Maximale Rundenzahl erreicht.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Deine Antwort (3/3)")).toBeNull();
    expect(screen.queryByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeNull();
    expect(screen.getByRole("button", { name: "Dialog beenden" })).toBeInTheDocument();
  });

  it("clears the local closing draft after final submission", async () => {
    const storageKey = "gustav.learning.dialog-closing-draft:student-1:course-1:task-dialog:session-1";
    const active = answeredSession();
    const completed = answeredSession({ status: "completed", closing_answer_md: "Fazit" });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ session: active }))
      .mockResolvedValueOnce(jsonResponse({ session: completed }));
    vi.stubGlobal("fetch", fetchMock);
    render(LearningDialogWorkspace, {
      props: { learnerSub: "student-1", courseId: "course-1", task: dialogTask }
    });

    await fireEvent.click(await screen.findByRole("button", { name: "Dialog beenden" }));
    await fireEvent.input(screen.getByLabelText("Fasse deine wichtigste Erkenntnis zusammen."), {
      target: { value: "Fazit" }
    });
    expect(window.sessionStorage.getItem(storageKey)).not.toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: "Endgültig abgeben" }));

    await waitFor(() => expect(window.sessionStorage.getItem(storageKey)).toBeNull());
    expect(fetchMock.mock.calls[1]?.[0]).toContain("/session-1/complete");
  });

  it("implements pausing as navigation without a dialog mutation", async () => {
    renderDialog(answeredSession());

    const pause = await screen.findByRole("link", { name: "Pausieren" });
    expect(pause).toHaveAttribute("href", "/learning/courses/course-1");
  });

  it("shows materials from opened modules in the partner context without pinning", async () => {
    const onOpenContext = vi.fn();
    const onCloseContextModule = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ session: answeredSession() })));
    render(LearningDialogWorkspace, {
      props: {
        learnerSub: "student-1",
        courseId: "course-1",
        task: dialogTask,
        contextModules: [
          {
            id: "module-current",
            title: "Grundlagen",
            current: true,
            closable: false,
            loaded: true,
            loading: false,
            error: null,
            items: [{
              key: "material:source",
              kind: "material",
              title: "Lange Quelle",
              position: 1,
              contextLabel: "Grundlagen",
              moduleId: "module-current",
              material: {
                id: "source",
                title: "Lange Quelle",
                kind: "markdown",
                body_md: "Ein langer Quellentext."
              }
            }]
          },
          {
            id: "module-extra",
            title: "Vertiefung",
            current: false,
            closable: true,
            loaded: true,
            loading: false,
            error: null,
            items: []
          }
        ],
        expandedContextModuleIds: ["module-extra"],
        onOpenContext,
        onCloseContextModule
      }
    });

    const context = await screen.findByRole("complementary", { name: "Dialogpartner und Sitzungsaktionen" });
    expect(within(context).getByRole("heading", { name: /Grundlagen/, level: 4 })).toBeInTheDocument();
    expect(within(context).getByText("Lange Quelle")).toBeInTheDocument();
    expect(within(context).getByText("Ein langer Quellentext.")).toBeInTheDocument();
    expect(within(context).queryByText("Angeheftet")).not.toBeInTheDocument();
    expect(within(context).queryByText("Material suchen")).not.toBeInTheDocument();
    await fireEvent.click(within(context).getByRole("button", { name: "Modul Vertiefung schließen" }));
    expect(onCloseContextModule).toHaveBeenCalledWith("module-extra");
  });

  it("does not render the removed source picker in the dialog sidebar", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ session: answeredSession() })));
    render(LearningDialogWorkspace, {
      props: {
        learnerSub: "student-1",
        courseId: "course-1",
        task: dialogTask,
        contextModules: []
      }
    });

    await screen.findByText("Archivarin");
    expect(screen.queryByText("Material suchen")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /anheften|lösen/i })).not.toBeInTheDocument();
  });

  it("hides all session actions in the completed read-only view", async () => {
    const current = answeredSession({ status: "completed", closing_answer_md: "Fazit" });
    const fetchMock = vi.fn(async () => jsonResponse({ session: current }));
    vi.stubGlobal("fetch", fetchMock);
    render(LearningDialogWorkspace, {
      props: {
        learnerSub: "student-1",
        courseId: "course-1",
        task: dialogTask,
        existingSessionId: "session-1",
        readOnly: true
      }
    });

    expect(await screen.findByText("Der Dialog wurde endgültig abgegeben. Die Rückmeldung wird erstellt.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Pausieren" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Antwort senden" })).toBeNull();
  });

  it("keeps dialog presentation in the layered learner stylesheet without hard-coded colors", () => {
    const source = readFileSync(path.resolve(currentDir, "LearningDialogWorkspace.svelte"), "utf8");
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const dialogBlocks = Array.from(css.matchAll(/\.dialog-[^{}]+\{[^{}]*\}/g), (match) => match[0]).join("\n");

    expect(source).not.toMatch(/<style(?:\s|>)/);
    expect(dialogBlocks).toContain(".dialog-workspace");
    expect(dialogBlocks).toContain(".dialog-sidebar");
    expect(dialogBlocks).toContain(".dialog-main");
    expect(dialogBlocks).toContain(".dialog-message--ai");
    expect(dialogBlocks).toContain(".dialog-message--student");
    expect(css).toContain("container-type: inline-size");
    expect(css).toContain("container-name: learning-dialog");
    expect(css).toContain("@container learning-dialog (min-width: 42.5rem)");
    expect(css).toContain("@container learning-dialog (min-width: 72rem)");
    expect(css).not.toContain("@container learning-dialog (min-width: 64rem)");
    expect(css).toContain("@container learning-dialog (max-width: 21.999rem)");
    expect(css).toContain("@supports not (container-type: inline-size)");
    expect(dialogBlocks).not.toContain("var(--color-success-soft)");
    expect(dialogBlocks).not.toContain("var(--color-accent-soft)");
    expect(dialogBlocks).not.toMatch(/#[0-9a-f]{3,8}/i);
  });
});
