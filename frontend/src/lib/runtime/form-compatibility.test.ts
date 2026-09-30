import { afterEach, expect, it, vi } from "vitest";
import { installFormCompatibility } from "./form-compatibility";

const NativeFormData = window.FormData;
const submitterDescriptor = Object.getOwnPropertyDescriptor(SubmitEvent.prototype, "submitter")!;
let restore = () => {};

afterEach(() => {
  restore();
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  Object.defineProperty(SubmitEvent.prototype, "submitter", submitterDescriptor);
});

function oldFormData() {
  vi.stubGlobal("FormData", class extends NativeFormData {
    constructor(form?: HTMLFormElement) { super(form); }
  });
}

it("leaves a correctly implemented browser unchanged", () => {
  restore = installFormCompatibility();
  expect(window.FormData).toBe(NativeFormData);
});

it("preserves submitter value, field order, files and the native FormData brand", () => {
  oldFormData();
  restore = installFormCompatibility();
  document.body.innerHTML = '<form><input name="intent" value="before"><button name="intent" value="submit">Abgeben</button><input name="intent" value="after"><input type="file" name="file"></form>';
  const form = document.querySelector("form")!;
  const button = form.querySelector("button")!;
  const data = new FormData(form, button);
  expect(data).toBeInstanceOf(NativeFormData);
  expect(data.getAll("intent")).toEqual(["before", "submit", "after"]);
  expect(data.get("file")).toBeInstanceOf(File);
  expect(form.querySelectorAll("input")).toHaveLength(3);
  expect(new FormData(form).getAll("intent")).toEqual(["before", "after"]);
});

it("respects external form association, disabled buttons and rejects foreign submitters", () => {
  oldFormData();
  restore = installFormCompatibility();
  document.body.innerHTML = '<form id="target"></form><button form="target" name="intent" value="submit">Abgeben</button><form id="other"></form>';
  const form = document.querySelector<HTMLFormElement>("#target")!;
  const button = document.querySelector("button")!;
  expect(new FormData(form, button).get("intent")).toBe("submit");
  button.disabled = true;
  expect(new FormData(form, button).has("intent")).toBe(false);
  expect(() => new FormData(document.querySelector<HTMLFormElement>("#other")!, button)).toThrow();
});

it("repairs Safari button submitter events without replaying clicks or submissions", async () => {
  Object.defineProperty(SubmitEvent.prototype, "submitter", { configurable: true, get: () => null });
  restore = installFormCompatibility();
  document.body.innerHTML = '<form><input required><button name="intent" value="submit">Abgeben</button></form>';
  const form = document.querySelector("form")!;
  const button = form.querySelector("button")!;
  const submitted = vi.fn((event: SubmitEvent) => {
    event.preventDefault();
    expect(event.submitter).toBe(button);
  });
  form.addEventListener("submit", submitted);
  button.click();
  expect(submitted).not.toHaveBeenCalled();
  form.querySelector("input")!.value = "Antwort";
  button.click();
  expect(submitted).toHaveBeenCalledOnce();
  await Promise.resolve();
});

it("does not borrow a canceled click for another form or a later submit event", async () => {
  Object.defineProperty(SubmitEvent.prototype, "submitter", { configurable: true, get: () => null });
  restore = installFormCompatibility();
  document.body.innerHTML = '<form><button>Abgeben</button></form><form id="other"></form>';
  const form = document.querySelector("form")!;
  const button = form.querySelector("button")!;
  button.addEventListener("click", (event) => event.preventDefault());
  button.click();
  const foreign = new SubmitEvent("submit", { cancelable: true });
  document.querySelector("#other")!.dispatchEvent(foreign);
  expect(foreign.submitter).toBeNull();
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  const later = new SubmitEvent("submit", { cancelable: true });
  form.dispatchEvent(later);
  expect(later.submitter).toBeNull();
});
