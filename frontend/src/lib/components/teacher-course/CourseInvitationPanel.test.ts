import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toCanvas, toDataURL } = vi.hoisted(() => ({
  toCanvas: vi.fn(async (..._args: unknown[]) => undefined),
  toDataURL: vi.fn(async (..._args: unknown[]) => "data:image/png;base64,qr")
}));

vi.mock("qrcode", () => ({ default: { toCanvas, toDataURL } }));

import CourseInvitationPanel from "./CourseInvitationPanel.svelte";

const invitation = {
  id: "invite-1",
  course_id: "course-1",
  invite_url: "https://app.localhost/invite#v1.exact-active-token",
  expires_at: "2026-08-16T12:00:00+00:00",
  created_at: "2026-08-15T12:00:00+00:00",
  redemption_count: 3,
  email_status: { pending: 1, sent: 4, failed: 1 }
};

describe("course invitation panel", () => {
  beforeEach(() => {
    toCanvas.mockClear();
    toDataURL.mockClear();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(async () => undefined) }
    });
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      value: null
    });
    history.replaceState({}, "", location.pathname);
  });

  afterEach(() => vi.restoreAllMocks());

  it("encodes exactly the active link with high error correction", async () => {
    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });

    await waitFor(() => expect(toCanvas).toHaveBeenCalled());
    const qrCall = toCanvas.mock.calls.at(-1) as unknown[];
    expect(qrCall[1]).toBe(invitation.invite_url);
    expect(qrCall[2]).toMatchObject({
      errorCorrectionLevel: "H",
      margin: 4
    });

    await fireEvent.click(screen.getByRole("button", { name: "Link kopieren" }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(invitation.invite_url);
  });

  it("uses native fullscreen and returns focus when it closes", async () => {
    const historyBack = vi.spyOn(history, "back").mockImplementation(() => undefined);
    const requestFullscreen = vi.fn(async () => undefined);
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen
    });
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: vi.fn(async () => undefined)
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    const trigger = screen.getByRole("button", { name: "Im Vollbild anzeigen" });
    await fireEvent.click(trigger);
    expect(requestFullscreen).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog", { name: "QR-Code im Vollbild" })).toHaveClass(
      "course-invite-fullscreen--open"
    );

    await fireEvent.click(screen.getByRole("button", { name: "Vollbild schließen" }));
    expect(trigger).toHaveFocus();
    expect(historyBack).toHaveBeenCalledTimes(1);
  });

  it("isolates the fallback, traps focus and cleans history on Escape", async () => {
    const historyBack = vi.spyOn(history, "back").mockImplementation(() => undefined);
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(async () => {
        throw new Error("denied");
      })
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    const trigger = screen.getByRole("button", { name: "Im Vollbild anzeigen" });
    await fireEvent.click(trigger);
    const overlay = screen.getByRole("dialog", { name: "QR-Code im Vollbild" });
    await waitFor(() => expect(overlay).toHaveClass("course-invite-fullscreen--fallback"));
    const linkField = screen.getByRole("textbox", { name: "Klassenlink" });
    expect(linkField.closest("label")).toHaveProperty("inert", true);
    const close = screen.getByRole("button", { name: "Vollbild schließen" });
    expect(close).toHaveFocus();

    await fireEvent.keyDown(window, { key: "Tab" });
    expect(close).toHaveFocus();
    await fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(close).toHaveFocus();

    await fireEvent.keyDown(window, { key: "Escape" });
    expect(overlay).not.toHaveClass("course-invite-fullscreen--open");
    expect(trigger).toHaveFocus();
    expect(linkField.closest("label")).toHaveProperty("inert", false);
    expect(historyBack).toHaveBeenCalledTimes(1);
  });

  it("lets browser back close the fallback without navigating back twice", async () => {
    const historyBack = vi.spyOn(history, "back").mockImplementation(() => undefined);
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(async () => {
        throw new Error("denied");
      })
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    const trigger = screen.getByRole("button", { name: "Im Vollbild anzeigen" });
    await fireEvent.click(trigger);
    const overlay = screen.getByRole("dialog", { name: "QR-Code im Vollbild" });
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitFor(() => expect(overlay).not.toHaveClass("course-invite-fullscreen--open"));
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(historyBack).not.toHaveBeenCalled();
  });

  it("keeps status and email retry controls privacy-limited", () => {
    render(CourseInvitationPanel, {
      props: {
        courseId: "course-1",
        courseTitle: "Informatik 9a",
        invitation,
        failedRecipients: ["failed@school.example"]
      }
    });
    expect(screen.getByText("3 Einlösungen")).toBeInTheDocument();
    expect(screen.getByText("1 ausstehend · 4 gesendet · 1 fehlgeschlagen")).toBeInTheDocument();
    expect(screen.getByText("failed@school.example")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fehlgeschlagene erneut senden" })).toBeInTheDocument();
  });
});
