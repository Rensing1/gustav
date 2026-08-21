import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import LearningDialogWorkspace from "./LearningDialogWorkspace.svelte";
import type { LearningSubmission, LearningTask } from "$lib/types/learning";
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

function failedSession(generationAttempts: number): TestSession {
  return answeredSession({
    turns: [
      ...answeredSession().turns,
      {
        id: "turn-2",
        round_nr: 2,
        student_message_md: "Eine zweite Beobachtung.",
        used_sentence_starter_md: null,
        used_sentence_starter_source: null,
        status: "failed",
        assistant_reply_md: null,
        sentence_starters: [],
        generation_attempts: generationAttempts
      }
    ]
  });
}

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
}

function renderDialog(
  current: TestSession,
  task: LearningTask = dialogTask,
  learnerSub: string | null = "student-1",
  extraProps: Record<string, unknown> = {}
) {
  const fetchMock = vi.fn(async () => jsonResponse({ session: current }));
  vi.stubGlobal("fetch", fetchMock);
  render(LearningDialogWorkspace, {
    props: {
      learnerSub,
      courseId: "course-1",
      task,
      ...extraProps
    }
  });
  return fetchMock;
}

describe("LearningDialogWorkspace", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("presents the opening message with real round progress in the shared task header", async () => {
    renderDialog(session(), dialogTask, "student-1", { taskTitle: "Aufgabe 2" });

    const context = await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
    expect(within(context).getByRole("heading", { name: "Aufgabe 2" })).toBeInTheDocument();
    expect(within(context).getByText("Untersuche die Quelle im Gespräch.")).toBeInTheDocument();
    expect(within(context).getByRole("region", { name: "Materialien zur Aufgabe" })).toBeInTheDocument();
    expect(within(context).queryByText("Dein Dialogpartner")).not.toBeInTheDocument();
    expect(within(context).queryByText("Eine sachkundige Gesprächspartnerin.")).not.toBeInTheDocument();

    const progress = within(context).getByRole("region", { name: "Gesprächsfortschritt" });
    expect(within(progress).getByText("Runde 0 von 3")).toBeInTheDocument();
    expect(within(progress).getByRole("progressbar", { name: "Runde 0 von 3" })).toHaveAttribute("aria-valuenow", "0");
    expect(within(progress).getByRole("progressbar", { name: "Runde 0 von 3" })).toHaveAttribute("aria-valuemax", "3");

    const currentQuestion = screen.getByRole("article", { name: "Aktuelle Frage" });
    expect(within(currentQuestion).getByText("Was fällt dir an der Quelle auf?")).toBeInTheDocument();
    expect(screen.queryByText("Aktuelle Frage")).toBeNull();
  });

  it("marks only the latest answerable AI message as the current question", async () => {
    renderDialog(answeredSession({
      round_count: 2,
      turns: [
        ...answeredSession().turns,
        {
          id: "turn-2",
          round_nr: 2,
          student_message_md: "Die Gegenseite fehlt.",
          used_sentence_starter_md: null,
          used_sentence_starter_source: null,
          status: "completed",
          assistant_reply_md: "Welche zusätzliche Perspektive wäre hilfreich?",
          sentence_starters: [],
          generation_attempts: 1
        }
      ]
    }));

    const context = await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
    const progress = within(context).getByRole("region", { name: "Gesprächsfortschritt" });
    expect(within(progress).getByText("Runde 2 von 3")).toBeInTheDocument();
    const currentQuestion = screen.getByRole("article", { name: "Aktuelle Frage" });
    expect(within(currentQuestion).getByText("Welche zusätzliche Perspektive wäre hilfreich?")).toBeInTheDocument();
    expect(within(currentQuestion).queryByText("Woran erkennst du diese Einseitigkeit?")).toBeNull();
    for (const avatar of screen.getAllByLabelText("Du")) {
      expect(avatar).toHaveTextContent("D");
    }
    expect(screen.queryByText("Aktuelle Frage")).toBeNull();
  });

  it("keeps configured sentence starters beside the composer", async () => {
    const hybridTask: LearningTask = {
      ...dialogTask,
      dialog: { ...dialogTask.dialog!, response_mode: "hybrid" }
    };
    renderDialog(
      session({
        dialog: hybridTask.dialog!,
        initial_sentence_starters: ["Mir fällt auf, dass …"],
        initial_starters_status: "completed"
      }),
      hybridTask
    );

    const composer = await screen.findByRole("region", { name: "Dialog fortsetzen" });
    const helpers = within(composer).getByRole("group", { name: "Hilfestellungen" });
    await fireEvent.click(within(helpers).getByRole("button", { name: "Mir fällt auf, dass …" }));
    expect(screen.getByLabelText("Deine Antwort (0/3)")).toHaveValue("Mir fällt auf, dass …");
  });

  it("does not invent helper prompts for free-text dialogs", async () => {
    renderDialog(session());

    const composer = await screen.findByRole("region", { name: "Dialog fortsetzen" });
    expect(within(composer).queryByRole("group", { name: "Hilfestellungen" })).toBeNull();
  });

  it("does not inject material actions into the conversation", async () => {
    renderDialog(answeredSession(), dialogTask, "student-1", {
      contextModules: [
        {
          id: "module-1",
          title: "Quellenanalyse",
          current: true,
          closable: false,
          loaded: true,
          loading: false,
          error: null,
          items: [
            {
              key: "material:rules",
              kind: "material",
              title: "Gesprächsregeln",
              position: 1,
              contextLabel: "Quellenanalyse",
              moduleId: "module-1",
              material: {
                id: "rules",
                title: "Gesprächsregeln",
                kind: "markdown",
                body_md: "Begründe Beobachtungen und frage nach Belegen."
              }
            }
          ]
        }
      ]
    });

    expect(await screen.findByRole("article", { name: "Aktuelle Frage" })).toBeInTheDocument();
    const transcript = screen.getByRole("log", { name: "Dialogverlauf" });
    expect(within(transcript).queryByRole("button", { name: "Gesprächsregeln" })).toBeNull();
  });

  it("places the AI safety notice where the learner writes", async () => {
    renderDialog(session());

    const taskContext = await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
    const composer = screen.getByRole("region", { name: "Dialog fortsetzen" });
    expect(within(taskContext).queryByRole("note")).toBeNull();
    expect(within(composer).getByRole("note")).toHaveTextContent(
      "Antworten können Fehler enthalten. Gib keine persönlichen oder vertraulichen Informationen ein."
    );
  });

  it("uses the shared task context instead of a dialog-specific briefing", async () => {
    renderDialog(session(), dialogTask, "student-1", { taskTitle: "Aufgabe 2" });

    const context = await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
    expect(within(context).getByRole("heading", { name: "Aufgabe 2" })).toBeInTheDocument();
    expect(within(context).getByText("KI-Dialog")).toBeInTheDocument();
    expect(within(context).getByText("Untersuche die Quelle im Gespräch.")).toBeInTheDocument();
    expect(within(context).getByRole("region", { name: "Materialien zur Aufgabe" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Gesprächsbriefing" })).toBeNull();
    expect(within(context).queryByText("Archivarin")).toBeNull();
  });

  it("hides completion controls before the first answered turn", async () => {
    renderDialog(session());

    expect(await screen.findByRole("article", { name: "Aktuelle Frage" })).toBeInTheDocument();
    const taskContext = screen.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const composer = screen.getByRole("region", { name: "Dialog fortsetzen" });
    expect(screen.getByLabelText("Deine Antwort (0/3)")).toBeInTheDocument();
    expect(screen.queryByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(taskContext).queryByRole("link", { name: "Pausieren" })).toBeNull();
    expect(within(taskContext).queryByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeNull();
    expect(within(taskContext).queryByRole("button", { name: "Antwort senden" })).toBeNull();
    expect(within(composer).getByRole("button", { name: "Antwort senden" })).toBeInTheDocument();
    expect(within(composer).getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeInTheDocument();
    expect(within(composer).getByRole("link", { name: "Pausieren" })).toBeInTheDocument();
  });

  it("uses the shared adjustable column separator in wide dialog layouts", async () => {
    const onPreviewTaskColumnRatio = vi.fn();
    const onCommitTaskColumnRatio = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ session: session() })));
    const { container } = render(
      LearningDialogWorkspace,
      {
        props: {
          learnerSub: "student-1",
          courseId: "course-1",
          task: dialogTask,
          taskColumnRatio: 57,
          onPreviewTaskColumnRatio,
          onCommitTaskColumnRatio
        }
      }
    );

    const separator = await screen.findByRole("separator", { name: "Spaltenbreite anpassen" });
    expect(separator).toHaveAttribute("aria-valuenow", "57");
    expect(container.querySelector(".dialog-layout")).toHaveStyle("--learner-task-column-ratio: 57%");

    await fireEvent.keyDown(separator, { key: "ArrowLeft" });
    expect(onPreviewTaskColumnRatio).toHaveBeenLastCalledWith(56);
    expect(onCommitTaskColumnRatio).toHaveBeenLastCalledWith(56);
  });

  it("offers a deliberate transition while keeping the closing prompt hidden", async () => {
    renderDialog(answeredSession());

    const taskContext = await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
    const composer = screen.getByRole("region", { name: "Dialog fortsetzen" });
    expect(within(taskContext).queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(taskContext).queryByRole("link", { name: "Pausieren" })).toBeNull();
    expect(within(composer).getByRole("button", { name: "Antwort senden" })).toBeInTheDocument();
    expect(within(composer).getByRole("button", { name: "Dialog beenden" })).toBeInTheDocument();
    expect(within(composer).getByRole("link", { name: "Pausieren" })).toBeInTheDocument();
    expect(screen.queryByText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeNull();
    expect(screen.getByLabelText("Deine Antwort (1/3)")).toBeInTheDocument();
  });

  it("opens and leaves the closing phase without a server mutation", async () => {
    const fetchMock = renderDialog(answeredSession());
    const endButton = await screen.findByRole("button", { name: "Dialog beenden" });

    await fireEvent.click(endButton);

    const taskContext = screen.getByRole("complementary", { name: "Aufgabe und Kontext" });
    const closing = screen.getByRole("region", { name: "Abschluss vorbereiten" });
    expect(screen.getByLabelText("Fasse deine wichtigste Erkenntnis zusammen.")).toBeInTheDocument();
    expect(within(taskContext).queryByRole("link", { name: "Pausieren" })).toBeNull();
    expect(within(taskContext).queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(closing).getByRole("button", { name: "Endgültig abgeben" })).toBeInTheDocument();
    expect(within(closing).getByRole("button", { name: "Zurück zum Dialog" })).toBeInTheDocument();
    expect(within(closing).getByRole("link", { name: "Pausieren" })).toBeInTheDocument();
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

  it("offers a failed AI response retry in the main action area", async () => {
    renderDialog(failedSession(2));

    const composer = await screen.findByRole("region", { name: "Dialog fortsetzen" });
    expect(within(composer).getByRole("button", { name: "KI-Antwort erneut versuchen" })).toBeInTheDocument();
    expect(within(composer).getByRole("button", { name: "Dialog beenden" })).toBeInTheDocument();
    expect(within(screen.getByRole("log", { name: "Dialogverlauf" })).queryByRole("button")).toBeNull();
    expect(screen.queryByText("Die KI-Antwort kann nicht erneut erzeugt werden.")).toBeNull();
  });

  it("removes the retry action after the third failed generation attempt", async () => {
    renderDialog(failedSession(3));

    const composer = await screen.findByRole("region", { name: "Dialog fortsetzen" });
    expect(within(composer).queryByRole("button", { name: "KI-Antwort erneut versuchen" })).toBeNull();
    expect(within(composer).getByText("Die KI-Antwort kann nicht erneut erzeugt werden.")).toBeInTheDocument();
    const endButton = within(composer).getByRole("button", { name: "Dialog beenden" });
    expect(endButton).toBeInTheDocument();
    expect(within(composer).getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeInTheDocument();

    await fireEvent.click(endButton);

    expect(screen.getByRole("region", { name: "Abschluss vorbereiten" })).toBeInTheDocument();
  });

  it("offers the allowed abort after a terminal first-turn failure", async () => {
    renderDialog(session({
      turns: [{
        id: "turn-1",
        round_nr: 1,
        student_message_md: "Die Quelle wirkt einseitig.",
        used_sentence_starter_md: null,
        used_sentence_starter_source: null,
        status: "failed",
        assistant_reply_md: null,
        sentence_starters: [],
        generation_attempts: 3
      }]
    }));

    const composer = await screen.findByRole("region", { name: "Dialog fortsetzen" });
    expect(within(composer).queryByRole("button", { name: "KI-Antwort erneut versuchen" })).toBeNull();
    expect(within(composer).queryByRole("button", { name: "Dialog beenden" })).toBeNull();
    expect(within(composer).getByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Dialog ohne Abgabe abbrechen" })).toHaveLength(1);
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

  it("forwards the final dialog submission so its feedback can be tracked", async () => {
    const active = answeredSession();
    const completed = answeredSession({ status: "completed", closing_answer_md: "Fazit" });
    const submission: LearningSubmission = {
      id: "11111111-1111-4111-8111-111111111111",
      attempt_nr: 1,
      kind: "dialog",
      dialog_session_id: completed.id,
      intent: "submit",
      analysis_status: "pending",
      created_at: "2026-08-20T10:00:00Z"
    };
    const onCompleted = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(jsonResponse({ session: active }))
        .mockResolvedValueOnce(jsonResponse({ session: completed, submission }))
    );
    render(LearningDialogWorkspace, {
      props: {
        learnerSub: "student-1",
        courseId: "course-1",
        task: dialogTask,
        onCompleted
      }
    });

    await fireEvent.click(await screen.findByRole("button", { name: "Dialog beenden" }));
    await fireEvent.input(screen.getByLabelText("Fasse deine wichtigste Erkenntnis zusammen."), {
      target: { value: "Fazit" }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Endgültig abgeben" }));

    await waitFor(() => expect(onCompleted).toHaveBeenCalledWith(submission));
  });

  it("shows completed feedback for the finished dialog in the main workspace", async () => {
    const completed = answeredSession({ status: "completed", closing_answer_md: "Fazit" });
    const submission: LearningSubmission = {
      id: "22222222-2222-4222-8222-222222222222",
      attempt_nr: 1,
      kind: "dialog",
      dialog_session_id: completed.id,
      intent: "submit",
      analysis_status: "completed",
      created_at: "2026-08-20T10:00:00Z",
      feedback_md: "**Stark:** Du belegst deine Einschätzung mit der Quelle."
    };

    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ session: completed })));
    render(LearningDialogWorkspace, {
      props: {
        learnerSub: "student-1",
        courseId: "course-1",
        task: dialogTask,
        historyByTask: { [dialogTask.id]: [submission] }
      }
    });
    const feedback = await screen.findByRole("region", { name: "Rückmeldung zum KI-Dialog" });
    expect(within(feedback).getByText("Stark:")).toBeInTheDocument();
    expect(within(feedback).getByText(/Du belegst deine Einschätzung/)).toBeInTheDocument();
  });

  it("implements pausing as navigation without a dialog mutation", async () => {
    renderDialog(answeredSession());

    const pause = await screen.findByRole("link", { name: "Pausieren" });
    expect(pause).toHaveAttribute("href", "/learning/courses/course-1");
  });

  it("shows materials from opened modules in the shared task context without pinning", async () => {
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

    const context = await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
    const focusedMaterials = within(context).getByRole("region", { name: "Materialien zur Aufgabe" });
    expect(within(focusedMaterials).getByText("Lange Quelle")).toBeInTheDocument();
    expect(within(focusedMaterials).getByText("Ein langer Quellentext.")).toBeInTheDocument();
    expect(within(context).queryByText("Angeheftet")).not.toBeInTheDocument();
    expect(within(context).queryByText("Material suchen")).not.toBeInTheDocument();
    await fireEvent.click(within(context).getByText("Weitere Materialien und eigene Abgaben"));
    expect(within(context).getByRole("heading", { name: "Vertiefung", level: 4 })).toBeInTheDocument();
    expect(within(context).getAllByText("Lange Quelle")).toHaveLength(1);
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

    await screen.findByRole("complementary", { name: "Aufgabe und Kontext" });
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
    expect(css).toContain("@container learning-dialog (min-width: 60rem)");
    expect(css).not.toContain("@container learning-dialog (min-width: 64rem)");
    expect(css).toContain("@container learning-dialog (max-width: 21.999rem)");
    expect(css).toContain("@supports not (container-type: inline-size)");
    expect(dialogBlocks).not.toContain("var(--color-success-soft)");
    expect(dialogBlocks).not.toContain("var(--color-accent-soft)");
    expect(dialogBlocks).not.toMatch(/#[0-9a-f]{3,8}/i);
  });

  it("keeps the integrated composer beside an internally scrolling transcript", () => {
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const mainRules = Array.from(css.matchAll(/\.dialog-main\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const transcriptRules = Array.from(css.matchAll(/\.dialog-transcript\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const composerRules = Array.from(css.matchAll(/\.dialog-composer[^,{]*\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");

    expect(mainRules).toContain("grid-template-rows: minmax(0, 1fr) auto");
    expect(mainRules).toContain("overflow: hidden");
    expect(transcriptRules).toContain("overflow-y: auto");
    expect(transcriptRules).toContain("align-content: start");
    expect(composerRules).toContain("border-block-start: 1px solid");
  });

  it("uses the shared context and established GUSTAV surfaces instead of a separate dialog theme", () => {
    const source = readFileSync(path.resolve(currentDir, "LearningDialogWorkspace.svelte"), "utf8");
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const workspaceRules = Array.from(css.matchAll(/\.dialog-workspace\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const layoutRules = Array.from(css.matchAll(/\.dialog-layout\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const sharedSidebarRules = Array.from(
      css.matchAll(/\.dialog-sidebar\.learner-task-context\s*\{[^{}]*\}/g),
      (match) => match[0]
    ).join("\n");
    const mainRules = Array.from(css.matchAll(/\.dialog-main\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const transcriptRules = Array.from(css.matchAll(/\.dialog-transcript\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const messageRules = Array.from(css.matchAll(/\.dialog-message\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const bubbleRules = Array.from(css.matchAll(/\.dialog-message__bubble\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const composerRules = Array.from(css.matchAll(/\.dialog-composer[^,{]*\s*\{[^{}]*\}/g), (match) => match[0]).join("\n");
    const actionRules = Array.from(
      css.matchAll(/\.dialog-workspace \.workspace-top-action\s*\{[^{}]*\}/g),
      (match) => match[0]
    ).join("\n");
    const workbenchRules = Array.from(
      css.matchAll(/\.learner-task-workbench--dialog\s*\{[^{}]*\}/g),
      (match) => match[0]
    ).join("\n");
    const nestedProseRules = Array.from(
      css.matchAll(/\.dialog-(?:main|sidebar)[^,{]*\.markdown-prose\s*\{[^{}]*\}/g),
      (match) => match[0]
    ).join("\n");

    expect(workspaceRules).not.toContain("--dialog-radius-panel");
    expect(workspaceRules).not.toContain("--dialog-radius-message");
    expect(layoutRules).toContain("gap: var(--space-4)");
    expect(source).toContain("<LearnerTaskContext");
    expect(source).toContain("roundCurrent={session.round_count}");
    expect(source).toContain("roundMaximum={session.dialog.max_rounds}");
    expect(source).not.toContain('class="dialog-progress"');
    expect(source).toContain("dialog-message__bubble");
    expect(source).not.toContain('class="dialog-reference-chip"');
    expect(source).not.toContain('class="learner-task-context dialog-sidebar"');
    expect(source).not.toContain("dialog-briefing");
    expect(source).not.toContain("dialog-materials-panel");
    expect(sharedSidebarRules).toContain("border: 1px solid");
    expect(sharedSidebarRules).toContain("background: var(--color-bg-surface)");
    expect(mainRules).toContain("border: 1px solid");
    expect(mainRules).not.toContain("border-inline-start: 3px solid");
    expect(mainRules).toContain("border-radius: var(--radius-xl)");
    expect(mainRules).toContain("background: var(--color-bg-surface)");
    expect(mainRules).toContain("box-shadow: none");
    expect(transcriptRules).toContain("align-content: start");
    expect(transcriptRules).toContain("grid-auto-rows: max-content");
    expect(messageRules).toContain("box-shadow: none");
    expect(messageRules).toContain("max-width:");
    expect(bubbleRules).toContain("border-radius: var(--radius-xl)");
    expect(composerRules).toContain("border: 0");
    expect(composerRules).toContain("border-block-start: 1px solid");
    expect(composerRules).not.toContain("border: 2px solid");
    expect(actionRules).not.toContain("border-radius: 999px");
    expect(layoutRules).toContain("40%");
    expect(workbenchRules).toContain("height: calc(100svh - 14rem)");
    expect(nestedProseRules).toContain("border: 0");
    expect(nestedProseRules).toContain("border-inline-start: 0");
  });
});
