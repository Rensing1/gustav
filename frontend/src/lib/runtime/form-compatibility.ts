/**
 * Repair the two submitter semantics SvelteKit needs on Safari 15.3.
 * Feature probes leave modern browsers unchanged. Only GUSTAV's submit buttons
 * are supported; native validation, FormData file handling and field order stay
 * intact. Call once before client routes; cleanup is provided for isolated tests.
 * This changes browser plumbing, never server actions or permissions.
 */
export function installFormCompatibility(): () => void {
  const NativeFormData = window.FormData;
  const form = document.createElement("form");
  const button = document.createElement("button");
  button.name = "gustav_submitter_probe";
  button.value = "submit";
  form.append(button);
  const needsFormData = new NativeFormData(form, button).get(button.name) !== button.value;
  let hasButtonSubmitter = false;
  form.hidden = true;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    hasButtonSubmitter = event.submitter === button;
  }, { once: true });
  // Connected forms reliably activate in WebKit; prevent any probe request.
  document.body.append(form);
  try { button.click(); } finally { form.remove(); }

  if (needsFormData) {
    window.FormData = class extends NativeFormData {
      constructor(form?: HTMLFormElement, submitter?: HTMLElement | null) {
        if (!form || !submitter) { super(form); return; }
        if (!(submitter instanceof HTMLButtonElement || submitter instanceof HTMLInputElement) || submitter.type !== "submit") {
          throw new TypeError("Expected a submit button.");
        }
        if (submitter.form !== form) throw new DOMException("Submitter belongs to a different form.", "NotFoundError");
        if (!submitter.name || submitter.matches(":disabled")) { super(form); return; }
        // A temporary successful control preserves order, even for external
        // form-associated buttons. Native FormData still handles every file.
        const field = document.createElement("input");
        field.type = "hidden";
        field.name = submitter.name;
        field.value = submitter.value;
        const association = submitter.getAttribute("form");
        if (association !== null) field.setAttribute("form", association);
        submitter.before(field);
        try { super(form); } finally { field.remove(); }
      }
    };
  }

  let clicked: HTMLButtonElement | HTMLInputElement | null = null;
  let clearClick = 0;
  const click = (event: MouseEvent) => {
    const target = event.target instanceof Element ? event.target.closest("button, input") : null;
    clicked = (target instanceof HTMLButtonElement || target instanceof HTMLInputElement) && target.type === "submit" ? target : null;
    // Real input dispatch may run microtasks before its submit default action.
    // Keep the submitter through activation, but not beyond this event task.
    window.clearTimeout(clearClick);
    clearClick = window.setTimeout(() => { clicked = null; }, 0);
  };
  const submit = (event: SubmitEvent) => {
    if (!event.submitter && clicked?.form === event.target) {
      Object.defineProperty(event, "submitter", { value: clicked });
    }
  };
  if (!hasButtonSubmitter) {
    document.addEventListener("click", click, true);
    document.addEventListener("submit", submit, true);
  }
  return () => {
    window.clearTimeout(clearClick);
    document.removeEventListener("click", click, true);
    document.removeEventListener("submit", submit, true);
    if (needsFormData) window.FormData = NativeFormData;
  };
}
