import { render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import LearningDialogTranscriptDocument from "./LearningDialogTranscriptDocument.svelte";

describe("LearningDialogTranscriptDocument", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads the existing learner-safe transcript and renders every contribution", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "session-1",
        status: "completed",
        round_count: 1,
        dialog: {
          partner_name: "Ada",
          partner_description_md: "Eine Gesprächspartnerin",
          opening_message_md: "Womit beginnen wir?",
          response_mode: "free_text",
          max_rounds: 8
        },
        closing_answer_md: "Mein Fazit.",
        initial_sentence_starters: [],
        initial_starters_status: "not_required",
        initial_generation_attempts: 0,
        turns: [
          {
            id: "turn-1",
            round_nr: 1,
            student_message_md: "Mit dem ersten Argument.",
            used_sentence_starter_md: null,
            used_sentence_starter_source: null,
            status: "completed",
            assistant_reply_md: "Dann prüfe das Gegenargument.",
            sentence_starters: [],
            generation_attempts: 1
          }
        ]
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(LearningDialogTranscriptDocument, {
      props: { courseId: "course-1", taskId: "task-1", sessionId: "session-1" }
    });

    expect(await screen.findByText("Womit beginnen wir?")).toBeInTheDocument();
    expect(screen.getByText("Mit dem ersten Argument.")).toBeInTheDocument();
    expect(screen.getByText("Dann prüfe das Gegenargument.")).toBeInTheDocument();
    expect(screen.getByText("Mein Fazit.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/learning/courses/course-1/tasks/task-1/dialog-sessions/session-1",
      { credentials: "include", cache: "no-store" }
    );
  });

  it("shows a contained error when the safe transcript is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));

    render(LearningDialogTranscriptDocument, {
      props: { courseId: "course-1", taskId: "task-1", sessionId: "session-1" }
    });

    expect(await screen.findByText("Der Dialogverlauf konnte nicht geladen werden.")).toBeInTheDocument();
  });
});
