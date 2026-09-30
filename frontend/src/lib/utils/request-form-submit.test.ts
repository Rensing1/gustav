import { afterEach, describe, expect, it, vi } from "vitest";
import { requestFormSubmit } from "./request-form-submit";

afterEach(() => document.body.replaceChildren());

function fixture() {
  document.body.innerHTML = '<form action="/default" method="post"><input name="answer" required><button type="submit" name="intent" value="submit" formaction="/final" formmethod="post">Abgeben</button></form>';
  const form = document.querySelector("form")!;
  const button = form.querySelector("button")!;
  Object.defineProperty(form, "requestSubmit", { value: undefined, configurable: true });
  const submitted = vi.fn((event: SubmitEvent) => event.preventDefault());
  form.addEventListener("submit", submitted);
  return { form, button, submitted };
}

describe("compatible form submission", () => {
  it("delegates to native requestSubmit without clicking the original button", () => {
    const { form, button } = fixture();
    const native = vi.fn();
    Object.defineProperty(form, "requestSubmit", { value: native });
    requestFormSubmit(form, button);
    expect(native).toHaveBeenCalledWith(button);
  });
  it("preserves validation without requestSubmit", () => {
    const { form, button, submitted } = fixture();
    requestFormSubmit(form, button);
    expect(submitted).not.toHaveBeenCalled();
    expect(form.querySelectorAll("button")).toHaveLength(1);
  });
  it("submits exactly once with the intended value and action, without reopening confirmation", () => {
    const { form, button, submitted } = fixture();
    form.querySelector("input")!.value = "Antwort";
    const reopen = vi.fn((event: MouseEvent) => event.preventDefault());
    button.addEventListener("click", reopen);
    let actual: HTMLButtonElement | null = null;
    form.addEventListener("submit", (event) => { actual = event.submitter as HTMLButtonElement; });
    requestFormSubmit(form, button);
    expect(reopen).not.toHaveBeenCalled();
    expect(submitted).toHaveBeenCalledOnce();
    expect(actual!.name).toBe("intent");
    expect(actual!.value).toBe("submit");
    expect(actual!.getAttribute("formaction")).toBe("/final");
    expect(actual!.getAttribute("formmethod")).toBe("post");
    expect(form.querySelectorAll("button")).toHaveLength(1);
  });
  it("respects formnovalidate and supports callers without a submitter", () => {
    const { form, button, submitted } = fixture();
    button.formNoValidate = true;
    // jsdom does not implement the submitter's validation override; inspect
    // that attribute here and leave native activation semantics to WebKit.
    form.querySelector("input")!.value = "Antwort";
    form.addEventListener("submit", (event) => expect((event.submitter as HTMLButtonElement).formNoValidate).toBe(true), { once: true });
    requestFormSubmit(form, button);
    expect(submitted).toHaveBeenCalledOnce();
    submitted.mockClear();
    form.querySelector("input")!.value = "Antwort";
    requestFormSubmit(form);
    expect(submitted).toHaveBeenCalledOnce();
  });
});
