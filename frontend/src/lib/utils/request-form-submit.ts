/**
 * Submit the existing GUSTAV form with validation and its submit event intact.
 * A temporary button preserves submitter attributes without replaying the
 * original click handler (which may open a confirmation). No permissions change.
 */
export function requestFormSubmit(form: HTMLFormElement, submitter?: HTMLButtonElement): void {
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit(submitter);
    return;
  }
  const button = submitter ? submitter.cloneNode(false) as HTMLButtonElement : document.createElement("button");
  button.type = "submit";
  button.removeAttribute("id");
  button.removeAttribute("form");
  button.hidden = true;
  form.append(button);
  try {
    button.click();
  } finally {
    button.remove();
  }
}
