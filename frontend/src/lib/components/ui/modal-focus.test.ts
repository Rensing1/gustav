import { afterEach, describe, expect, it, vi } from "vitest";
import { modalFocus } from "./modal-focus";

describe("shared modal focus", () => {
  afterEach(() => document.body.replaceChildren());
  it("focuses within the dialog, cycles Tab and returns to the opener", async () => {
    document.body.innerHTML = '<button id="opener">Öffnen</button><div role="dialog" aria-modal="true"><button>Schließen</button><input aria-label="Titel"></div>';
    const opener = document.querySelector<HTMLButtonElement>("#opener")!;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    opener.focus();
    const close = vi.fn();
    const action = modalFocus(dialog, close);
    await Promise.resolve();
    expect(dialog.contains(document.activeElement)).toBe(true);
    const first = dialog.querySelector("button")!;
    const last = dialog.querySelector("input")!;
    last.focus();
    last.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(first);
    first.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(last);
    last.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    expect(close).toHaveBeenCalledTimes(1);
    action.destroy();
    expect(document.activeElement).toBe(opener);
  });
  it("does not close an underlying drawer when another modal is above it", async () => {
    document.body.innerHTML = '<div role="dialog" aria-modal="true"><button>Drawer</button></div><div role="dialog" aria-modal="true"><button>Abbrechen</button></div>';
    const [drawer, dialog] = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]'));
    const closeDrawer = vi.fn();
    const closeDialog = vi.fn();
    const first = modalFocus(drawer, closeDrawer);
    const second = modalFocus(dialog, closeDialog);
    await Promise.resolve();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", cancelable: true }));
    expect(closeDrawer).not.toHaveBeenCalled();
    expect(closeDialog).toHaveBeenCalledTimes(1);
    second.destroy(); first.destroy();
  });
});
