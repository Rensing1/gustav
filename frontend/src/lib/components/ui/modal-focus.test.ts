import { afterEach, describe, expect, it, vi } from "vitest";
import { containModalFocus, modalFocus } from "./modal-focus";

describe("shared modal focus", () => {
  afterEach(() => document.body.replaceChildren());
  it("redirects direct focus into an active modal and stops after cleanup", () => {
    document.body.innerHTML = '<button id="outside">Außen</button><div role="dialog" aria-modal="true"><button id="inside">Schließen</button></div>';
    const outside = document.querySelector<HTMLButtonElement>("#outside")!;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    const inside = document.querySelector<HTMLButtonElement>("#inside")!;
    let active = true;
    const stop = containModalFocus(dialog, () => inside.focus(), () => active);

    outside.focus();
    expect(inside).toHaveFocus();

    active = false;
    outside.focus();
    expect(outside).toHaveFocus();

    active = true;
    stop();
    inside.focus();
    outside.focus();
    expect(outside).toHaveFocus();
  });

  it("isolates and restores background semantics and pointer interaction without inert", async () => {
    document.body.innerHTML = '<main aria-hidden="false" style="pointer-events:auto"><button id="opener">Öffnen</button></main><div class="overlay"><div role="dialog" aria-modal="true"><button>Schließen</button></div></div>';
    const background = document.querySelector("main")!;
    const opener = document.querySelector<HTMLButtonElement>("#opener")!;
    opener.focus();
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    const action = modalFocus(dialog, vi.fn());
    await Promise.resolve();
    expect(background).toHaveAttribute("aria-hidden", "true");
    expect(background.style.pointerEvents).toBe("none");
    opener.focus();
    expect(dialog.contains(document.activeElement)).toBe(true);
    action.destroy();
    expect(background).toHaveAttribute("aria-hidden", "false");
    expect(background.style.pointerEvents).toBe("auto");
    expect(opener).toHaveFocus();
  });
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
