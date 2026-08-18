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

  it("keeps the high-resolution QR bitmap without the library's fixed display size", async () => {
    toCanvas.mockImplementationOnce(async (...args: unknown[]) => {
      const target = args[0] as HTMLCanvasElement;
      // qrcode sets both the bitmap resolution and an inline CSS size. The
      // latter must not be allowed to widen the narrow invitation drawer.
      target.width = 1024;
      target.height = 1024;
      target.style.width = "1024px";
      target.style.height = "1024px";
    });

    const { container } = render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    const canvas = container.querySelector("canvas");

    await waitFor(() => expect(canvas?.width).toBe(1024));
    expect(canvas?.height).toBe(1024);
    expect(canvas?.style.width).toBe("");
    expect(canvas?.style.height).toBe("");
    expect(screen.getByRole("button", { name: "Im Vollbild anzeigen" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Schul-E-Mail-Adressen/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Einladungen senden" })).toBeInTheDocument();
  });

  it("uses native fullscreen and returns focus when it closes", async () => {
    const historyBack = vi.spyOn(history, "back").mockImplementation(() => undefined);
    let fullscreenElement: Element | null = null;
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement
    });
    const requestFullscreen = vi.fn(async function (this: HTMLElement) {
      fullscreenElement = this;
    });
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen
    });
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: vi.fn(async () => {
        fullscreenElement = null;
      })
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
    expect(screen.getByRole("dialog", { name: "QR-Code im Vollbild" })).not.toHaveClass(
      "course-invite-fullscreen--fallback"
    );

    await fireEvent.click(screen.getByRole("button", { name: "Vollbild schließen" }));
    expect(trigger).toHaveFocus();
    expect(historyBack).toHaveBeenCalledTimes(1);
  });

  it("uses the page-filling fallback when fullscreen resolves without becoming active", async () => {
    vi.spyOn(history, "back").mockImplementation(() => undefined);
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(async () => undefined)
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Im Vollbild anzeigen" }));

    const overlay = screen.getByRole("dialog", { name: "QR-Code im Vollbild" });
    await waitFor(() => expect(overlay).toHaveClass("course-invite-fullscreen--fallback"));
  });

  it("uses the fallback when fullscreen disappears before the next UI turn", async () => {
    vi.spyOn(history, "back").mockImplementation(() => undefined);
    let fullscreenElement: Element | null = null;
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement
    });
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(async function (this: HTMLElement) {
        fullscreenElement = this;
        window.setTimeout(() => {
          fullscreenElement = null;
        }, 0);
      })
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Im Vollbild anzeigen" }));

    const overlay = screen.getByRole("dialog", { name: "QR-Code im Vollbild" });
    await waitFor(() => expect(overlay).toHaveClass("course-invite-fullscreen--fallback"));
  });

  it("uses the fallback when the fullscreen request never settles", async () => {
    vi.spyOn(history, "back").mockImplementation(() => undefined);
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(() => new Promise<void>(() => undefined))
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Im Vollbild anzeigen" }));

    const overlay = screen.getByRole("dialog", { name: "QR-Code im Vollbild" });
    await waitFor(
      () => expect(overlay).toHaveClass("course-invite-fullscreen--fallback"),
      { timeout: 1000 }
    );
  });

  it("does not activate the fallback after fullscreen was already closed", async () => {
    vi.spyOn(history, "back").mockImplementation(() => undefined);
    let rejectFullscreen: ((reason?: unknown) => void) | undefined;
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(
        () =>
          new Promise<void>((_resolve, reject) => {
            rejectFullscreen = reject;
          })
      )
    });

    render(CourseInvitationPanel, {
      props: { courseId: "course-1", courseTitle: "Informatik 9a", invitation }
    });
    await fireEvent.click(screen.getByRole("button", { name: "Im Vollbild anzeigen" }));
    await fireEvent.click(screen.getByRole("button", { name: "Vollbild schließen" }));
    rejectFullscreen?.(new Error("denied"));

    const linkField = screen.getByRole("textbox", { name: "Klassenlink" });
    await waitFor(() => expect(linkField.closest("label")?.inert).not.toBe(true));
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
