import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Execute the shipped Keycloak enhancement against a real DOM, without copying its logic.
const source = readFileSync("../keycloak/themes/gustav/login/resources/js/verify-email.js", "utf8");
const now = new Date("2026-01-01T12:00:00Z").getTime();
const template = "Bitte warte {seconds} Sekunden.";
const key = (tab = "tab-a") => 'gustav:verify-cooldown:' + JSON.stringify([
  "https://id.localhost", "/realms/gustav/login-actions/required-action", "gustav-web", tab,
]);
function markup(error = "", tab = "tab-a") {
  return `<section data-verification-wait data-cooldown-template="${template}"
    data-resend-success="Mail erneut gesendet." data-resend-failure="Versand fehlgeschlagen.">
    <h1>E-Mail bestätigen</h1>
    ${error ? `<div data-verification-error role="alert">${error}</div>` : ""}
    <p data-resend-status role="status" hidden></p>
    <form data-verification-resend method="post" action="https://id.localhost/realms/gustav/login-actions/required-action?client_id=gustav-web&amp;tab_id=${tab}">
      <button type="submit">Erneut senden</button>
    </form></section>`;
}
let listeners: EventListener[];
function load(error = "", tab = "tab-a") {
  document.body.innerHTML = markup(error, tab);
  new Function(source)();
}
function button() { return document.querySelector("button") as HTMLButtonElement; }
function status() { return document.querySelector("[data-resend-status]") as HTMLElement; }
async function submit() {
  document.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe("Keycloak verification email enhancement", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now));
    sessionStorage.clear();
    listeners = [];
    const original = document.addEventListener.bind(document);
    vi.spyOn(document, "addEventListener").mockImplementation((type, listener, options) => {
      if (type === "submit") listeners.push(listener as EventListener);
      original(type, listener, options);
    });
  });
  afterEach(() => {
    for (const listener of listeners) document.removeEventListener("submit", listener);
    document.body.innerHTML = "";
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it("keeps the absolute deadline after reload and expires after a background time jump", () => {
    load("Bitte warte 30 Sekunden.");
    const deadline = sessionStorage.getItem(key());
    expect(button()).toBeDisabled();
    vi.clearAllTimers();
    vi.setSystemTime(new Date(now + 12_000));
    load();
    expect(sessionStorage.getItem(key())).toBe(deadline);
    expect(document.querySelector('[role="timer"]')).toHaveTextContent("Bitte warte 18 Sekunden.");
    expect(button()).toBeDisabled();
    vi.setSystemTime(new Date(now + 37_000));
    vi.advanceTimersByTime(250);
    expect(button()).toBeEnabled();
    expect(sessionStorage.getItem(key())).toBeNull();
    expect(document.querySelector('[role="timer"]')).toBeNull();
  });
  it("ignores expired or invalid storage and isolates authentication tabs", () => {
    sessionStorage.setItem(key(), String(now + 30_000));
    load("", "tab-b");
    expect(button()).toBeEnabled();
    for (const value of ["invalid", String(now - 1)]) {
      sessionStorage.setItem(key(), value);
      load();
      expect(button()).toBeEnabled();
      expect(sessionStorage.getItem(key())).toBeNull();
    }
  });
  it("keeps server enforcement and the form usable when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    load("Bitte warte 2 Sekunden.");
    expect(button()).toBeDisabled();
    vi.advanceTimersByTime(2_000);
    expect(button()).toBeEnabled();
  });
  it("replaces an old error with success only after a successful resend", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, text: async () => markup() });
    vi.stubGlobal("fetch", fetch);
    load("Vorheriger Fehler");
    await submit();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: "POST", credentials: "same-origin" });
    expect(document.querySelector("[data-verification-error]")).toBeNull();
    expect(status()).toHaveTextContent("Mail erneut gesendet.");
    expect(status()).not.toHaveAttribute("hidden");
    expect(button()).toBeEnabled();
  });
  it("shows a server cooldown without a stale success notice or duplicate request", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, text: async () => markup("Bitte warte 10 Sekunden.") });
    vi.stubGlobal("fetch", fetch);
    load();
    status().textContent = "Alte Erfolgsmeldung";
    await submit();
    expect(button()).toBeDisabled();
    expect(status()).toHaveAttribute("hidden");
    expect(status()).toBeEmptyDOMElement();
    await submit();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it.each(["server", "network"])("shows a recoverable %s failure without claiming success", async kind => {
    vi.stubGlobal("fetch", kind === "server"
      ? vi.fn().mockResolvedValue({ ok: false, text: async () => '<div role="alert">Mailserver nicht erreichbar.</div>' })
      : vi.fn().mockRejectedValue(new Error("offline")));
    load();
    await submit();
    expect(status()).toHaveTextContent(kind === "server" ? "Mailserver nicht erreichbar." : "Versand fehlgeschlagen.");
    expect(status()).not.toHaveAttribute("hidden");
    expect(button()).toBeEnabled();
  });
});
