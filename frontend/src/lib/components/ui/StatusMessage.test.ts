import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import StatusMessage from "./StatusMessage.svelte";

describe("StatusMessage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("announces action errors assertively and exposes their recovery action", async () => {
    const onAction = vi.fn();

    render(StatusMessage, {
      props: {
        tone: "error",
        title: "Simulation konnte nicht hinzugefügt werden",
        description: "Entferne die externen Verweise und wähle die Datei erneut aus.",
        actionLabel: "Andere Datei wählen",
        onAction
      }
    });

    const message = screen.getByRole("alert");
    expect(message).toHaveAttribute("aria-live", "assertive");
    expect(message).toHaveAttribute("aria-atomic", "true");
    expect(message).toHaveClass("status-message--error");
    expect(screen.getByText("Simulation konnte nicht hinzugefügt werden")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Andere Datei wählen" }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("keeps progress visible and marks the region as busy", async () => {
    render(StatusMessage, {
      props: {
        tone: "progress",
        title: "Rückmeldung wird erstellt …"
      }
    });

    const message = screen.getByRole("status");
    expect(message).toHaveAttribute("aria-live", "polite");
    expect(message).toHaveAttribute("aria-busy", "true");

    await vi.advanceTimersByTimeAsync(120_000);
    expect(screen.getByText("Rückmeldung wird erstellt …")).toBeInTheDocument();
  });

  it("dismisses success after six visible seconds", async () => {
    const onDismiss = vi.fn();
    render(StatusMessage, {
      props: {
        tone: "success",
        title: "Material gespeichert",
        onDismiss
      }
    });

    expect(screen.getByRole("status")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(5_999);
    expect(screen.getByRole("status")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("pauses the success timer while the message is hovered", async () => {
    render(StatusMessage, {
      props: {
        tone: "success",
        title: "Rückmeldung ist bereit"
      }
    });

    const message = screen.getByRole("status");
    await vi.advanceTimersByTimeAsync(3_000);
    await fireEvent.mouseEnter(message);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(screen.getByRole("status")).toBeInTheDocument();

    await fireEvent.mouseLeave(message);
    await vi.advanceTimersByTimeAsync(2_999);
    expect(screen.getByRole("status")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not dismiss while keyboard focus remains inside the message", async () => {
    render(StatusMessage, {
      props: {
        tone: "success",
        title: "Rückmeldung ist bereit",
        actionLabel: "Ansehen",
        onAction: vi.fn()
      }
    });

    const action = screen.getByRole("button", { name: "Ansehen" });
    await vi.advanceTimersByTimeAsync(3_000);
    action.focus();
    await fireEvent.focusIn(action);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(screen.getByRole("status")).toBeInTheDocument();

    action.blur();
    await fireEvent.focusOut(action);
    await vi.advanceTimersByTimeAsync(3_000);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("starts the success timer when a running message becomes complete", async () => {
    const onDismiss = vi.fn();
    const view = render(StatusMessage, {
      props: {
        tone: "progress",
        title: "Rückmeldung wird erstellt …",
        onDismiss
      }
    });

    await vi.advanceTimersByTimeAsync(20_000);
    await view.rerender({ tone: "success", title: "Rückmeldung ist bereit", onDismiss });
    await vi.advanceTimersByTimeAsync(5_999);
    expect(screen.getByRole("status")).toHaveTextContent("Rückmeldung ist bereit");
    await vi.advanceTimersByTimeAsync(1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("does not expose a live-region role for a static hint", () => {
    render(StatusMessage, {
      props: {
        tone: "info",
        title: "Hinweis zur Bedienung",
        announcement: "off"
      }
    });

    const message = screen.getByText("Hinweis zur Bedienung").closest("section");
    expect(message).not.toHaveAttribute("role");
    expect(message).not.toHaveAttribute("aria-live");
  });

  it("counts only time while the page is visible", async () => {
    render(StatusMessage, { props: { tone: "success", title: "Gespeichert" } });

    await vi.advanceTimersByTimeAsync(2_000);
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(20_000);
    expect(screen.getByRole("status")).toBeInTheDocument();

    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(4_000);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
