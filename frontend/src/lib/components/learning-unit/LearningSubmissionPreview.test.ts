import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import LearningSubmissionPreview from "./LearningSubmissionPreview.svelte";
import type { LearningSubmission } from "$lib/types/learning";

const submission: LearningSubmission = {
  id: "final", intent: "submit", kind: "text", attempt_nr: 1,
  created_at: "2026-09-17T07:42:00Z", analysis_status: "completed",
  text_body: "**Eigene Lösung** mit [Quelle](https://example.com).",
  feedback_md: "Richtig zugeordnet.",
  analysis_json: { schema: "criteria.v2", criteria_results: [{ criterion: "EVA", score: 8, max_score: 10, explanation_md: "Gut erklärt." }] }
};
const props = (overrides = {}) => ({ courseId: "course", taskId: "task", taskTitle: "Ampel", hasSubmission: true,
  state: { status: "loaded" as const, submission }, ...overrides });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("LearningSubmissionPreview", () => {
  it("shows own plain answer immediately and nests independent disclosures only after expansion", async () => {
    render(LearningSubmissionPreview, props());
    expect(screen.getByText("Meine Abgabe")).toBeVisible();
    expect(screen.getByText(/Eigene Lösung mit Quelle/)).toBeVisible();
    expect(screen.queryByText("Rückmeldung", { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Ausklappen" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await fireEvent.click(toggle);
    expect(screen.getByRole("link", { name: "Quelle" })).toBeVisible();
    const feedback = screen.getByText("Rückmeldung", { exact: true }).closest("details")!;
    const evaluation = screen.getByText("Auswertung", { exact: true }).closest("details")!;
    expect(feedback.open).toBe(false);
    expect(evaluation.open).toBe(false);
    feedback.open = true;
    expect(evaluation.open).toBe(false);
    toggle.focus();
    await fireEvent.click(screen.getByRole("button", { name: "Einklappen" }));
    expect(toggle).toHaveFocus();
    expect(screen.queryByText("Rückmeldung", { exact: true })).not.toBeInTheDocument();
    await fireEvent.click(toggle);
    expect(screen.getByText("Rückmeldung", { exact: true }).closest("details")).not.toHaveAttribute("open");
  });

  it("resets disclosures when the selected snapshot changes", async () => {
    const view = render(LearningSubmissionPreview, props());
    await fireEvent.click(screen.getByRole("button", { name: "Ausklappen" }));
    await view.rerender(props({ state: { status: "loaded", submission: { ...submission, id: "new" } } }));
    expect(screen.getByRole("button", { name: "Ausklappen" })).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps the same snapshot expanded during a background update", async () => {
    const view = render(LearningSubmissionPreview, props());
    await fireEvent.click(screen.getByRole("button", { name: "Ausklappen" }));
    await view.rerender(props({ state: { status: "loading", submission } }));
    expect(screen.getByRole("button", { name: "Einklappen" })).toBeVisible();
  });

  it("omits pointless expansion for short answers without more content", () => {
    render(LearningSubmissionPreview, props({ state: { status: "loaded", submission: { ...submission, text_body: "Kurz.", feedback_md: null, analysis_json: null } } }));
    expect(screen.getByText("Kurz.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Ausklappen" })).not.toBeInTheDocument();
  });

  it("labels a saved draft without calling it a final submission", () => {
    render(LearningSubmissionPreview, props({ state: { status: "loaded", submission: { ...submission, intent: "feedback" } } }));
    expect(screen.getByText("Mein Entwurf")).toBeVisible();
    expect(screen.getByText("Noch nicht abgegeben")).toBeVisible();
    expect(screen.queryByText("Abgegeben", { exact: true })).not.toBeInTheDocument();
  });

  it("retains the final answer while offering the newer draft separately", async () => {
    const resume = vi.fn();
    render(LearningSubmissionPreview, props({ newerDraft: true, onContinueDraft: resume }));
    expect(screen.getByText("Neuerer Entwurf vorhanden")).toBeVisible();
    await fireEvent.click(screen.getByRole("button", { name: "Entwurf weiterbearbeiten" }));
    expect(resume).toHaveBeenCalledOnce();
    expect(screen.getByText("Meine Abgabe")).toBeVisible();
  });

  it("does not render an empty answer block and allows local load retries", async () => {
    const retry = vi.fn();
    const view = render(LearningSubmissionPreview, props({ hasSubmission: false, state: undefined }));
    expect(screen.queryByText("Meine Abgabe")).not.toBeInTheDocument();
    await view.rerender(props({ onLoad: retry, state: { status: "failed", submission: null } }));
    expect(screen.getByText("Abgabe konnte nicht geladen werden")).toBeVisible();
    await fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(retry).toHaveBeenCalled();
  });

  it.each(["image/png", "application/pdf", "application/octet-stream"])("loads full file view only on expansion: %s", async (mime) => {
    render(LearningSubmissionPreview, props({ state: { status: "loaded", submission: {
      ...submission, kind: mime.startsWith("image/") ? "image" : "file", text_body: null,
      files: [{ mime, size: 2048, url: "/private/file", download_url: "/private/file?download=1" }]
    } } }));
    expect(screen.queryByTitle("Abgabe zu Ampel")).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Ausklappen" }));
    expect(screen.getByRole("link", { name: "Datei öffnen" })).toHaveAttribute("href", "/private/file");
    if (mime === "application/pdf") expect(screen.getByTitle("Abgabe zu Ampel")).toBeVisible();
  });

  it.each([
    ["application/x.makecode.hex", '# makecode.evidence.v1\n\n### file: "main.py"\n```python\nprint("hello")\n```', "Codeansicht"],
    ["application/x.scratch.sb3", "# scratch.evidence.v2\n\n## Stage\nStart", "Strukturansicht"],
    ["application/x.filius.fls", "# filius.evidence.v1\n\n## Netzwerk\nServer", "Strukturansicht"]
  ])("uses the existing artifact renderer only in the full view: %s", async (mime, text, label) => {
    render(LearningSubmissionPreview, props({ state: { status: "loaded", submission: {
      ...submission, kind: "file", text_body: text,
      files: [{ mime, size: 2048, url: "/file", download_url: "/download" }]
    } } }));
    expect(screen.queryByText(label)).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Ausklappen" }));
    expect(screen.getByText(label)).toBeVisible();
    expect(screen.getByRole("link", { name: "Originaldatei herunterladen" })).toHaveAttribute("href", "/download");
    expect(screen.queryByRole("link", { name: "Datei öffnen" })).not.toBeInTheDocument();
  });

  it("loads a dialog transcript only after expanding its closing answer", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      dialog: { partner_name: "Partner", opening_message_md: "Begründe deine Beobachtung." }, turns: []
    }) });
    vi.stubGlobal("fetch", fetcher);
    render(LearningSubmissionPreview, props({ state: { status: "loaded", submission: {
      ...submission, kind: "dialog", dialog_session_id: "session", text_body: "Mein Fazit."
    } } }));
    expect(screen.getByText("Mein Fazit.")).toBeVisible();
    expect(fetcher).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole("button", { name: "Ausklappen" }));
    expect(await screen.findByText("Begründe deine Beobachtung.")).toBeVisible();
    expect(fetcher.mock.calls[0][0]).toContain("/dialog-sessions/session");
  });

  it.each(["pending", "failed"])("keeps stored work readable when analysis is %s", async (status) => {
    render(LearningSubmissionPreview, props({ state: { status: "loaded", submission: {
      ...submission, analysis_status: status, feedback_md: null, analysis_json: null
    } } }));
    await fireEvent.click(screen.getByRole("button", { name: "Ausklappen" }));
    expect(screen.getByText(status === "pending" ? "Rückmeldung wird erstellt …" : "Rückmeldung konnte nicht erstellt werden")).toBeVisible();
    expect(screen.queryByText("Auswertung", { exact: true })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quelle" })).toBeVisible();
  });

  it("labels a partial H5P result as a saved but unfinished handling", () => {
    render(LearningSubmissionPreview, props({ h5pCompleted: false, state: { status: "loaded", submission: {
      ...submission, kind: "h5p", text_body: null, score_raw: 4, score_max: 5, feedback_md: null, analysis_json: null
    } } }));
    expect(screen.getByText("Meine Bearbeitung")).toBeVisible();
    expect(screen.getByText("Noch nicht abgeschlossen")).toBeVisible();
    expect(screen.getByText("Zuletzt 4/5 Punkte erreicht.")).toBeVisible();
    expect(screen.queryByText("Meine Abgabe")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ausklappen" })).not.toBeInTheDocument();
  });

  it("keeps an earlier H5P completion visible beside the latest lower score", () => {
    render(LearningSubmissionPreview, props({ h5pCompleted: true, state: { status: "loaded", submission: {
      ...submission, kind: "h5p", text_body: null, score_raw: 0, score_max: 1, feedback_md: null, analysis_json: null
    } } }));
    expect(screen.getByText("Abgeschlossen")).toBeVisible();
    expect(screen.getByText("Zuletzt 0/1 Punkte erreicht.")).toBeVisible();
  });

  it("reacts to an earlier full score added to the live H5P history", async () => {
    const partial = {
      ...submission,
      id: "h5p-partial",
      kind: "h5p" as const,
      text_body: null,
      score_raw: 0,
      score_max: 1,
      feedback_md: null,
      analysis_json: null
    };
    const full = {
      ...partial,
      id: "h5p-full",
      attempt_nr: 2,
      score_raw: 1
    };
    const view = render(LearningSubmissionPreview, props({
      h5pCompleted: false,
      h5pHistory: [partial],
      state: { status: "loaded", submission: partial }
    }));
    expect(screen.getByText("Noch nicht abgeschlossen", { exact: true })).toBeVisible();

    await view.rerender(props({
      h5pCompleted: false,
      h5pHistory: [partial, full],
      state: { status: "loaded", submission: partial }
    }));

    expect(screen.getByText("Abgeschlossen", { exact: true })).toBeVisible();
  });
});
