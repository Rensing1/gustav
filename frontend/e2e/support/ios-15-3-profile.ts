import type { BrowserContext } from "@playwright/test";
import { webBase } from "./e2e-env";

export type BrowserCompatibilityProfile = "camera" | "combined" | "modern";

/** Remove only the app APIs missing on the supported iPadOS 15.3 baseline. */
export async function installBrowserCompatibilityProfile(context: BrowserContext, profile: BrowserCompatibilityProfile): Promise<void> {
  await context.addInitScript(({ origin, profile }) => {
    if (location.origin !== origin) return;
    if (profile === "modern") return;
    const remove = (object: object, key: string) => { Object.defineProperty(object, key, { value: undefined, configurable: true, writable: true }); };
    remove(Promise, "withResolvers");
    if (profile !== "combined") return;
    remove(Array.prototype, "at");
    remove(Array.prototype, "findLast");
    remove(Object, "hasOwn");
    remove(window, "structuredClone");
    remove(crypto, "randomUUID");
    remove(HTMLFormElement.prototype, "requestSubmit");
    // Safari 15.3 has SubmitEvent, but loses the submitter for buttons; its
    // FormData constructor silently ignores the newer second argument.
    const submitter = Object.getOwnPropertyDescriptor(SubmitEvent.prototype, "submitter")!.get!;
    Object.defineProperty(SubmitEvent.prototype, "submitter", {
      configurable: true,
      get() {
        const element = submitter.call(this);
        return element instanceof HTMLButtonElement ? null : element;
      }
    });
    const NativeFormData = window.FormData;
    window.FormData = class extends NativeFormData {
      constructor(form?: HTMLFormElement) { super(form); }
    };
    if (typeof HTMLDialogElement !== "undefined") {
      remove(HTMLDialogElement.prototype, "show");
      remove(HTMLDialogElement.prototype, "showModal");
      remove(HTMLDialogElement.prototype, "close");
    }
    delete (HTMLElement.prototype as Partial<HTMLElement>).inert;
  }, { origin: new URL(webBase).origin, profile });
}
