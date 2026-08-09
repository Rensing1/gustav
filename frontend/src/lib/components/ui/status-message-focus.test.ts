import { afterEach, describe, expect, it, vi } from "vitest";

import { focusActionError } from "./status-message-focus";

describe("focusActionError", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("focuses the first invalid field before falling back to the message", () => {
    const message = document.createElement("section");
    const field = document.createElement("input");
    field.setAttribute("aria-invalid", "true");
    document.body.append(message, field);
    const scrollIntoView = vi.fn();
    field.scrollIntoView = scrollIntoView;

    focusActionError(message, field);

    expect(document.activeElement).toBe(field);
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
  });

  it("focuses an actionable error message when no invalid field exists", () => {
    const message = document.createElement("section");
    message.tabIndex = -1;
    document.body.append(message);
    const scrollIntoView = vi.fn();
    message.scrollIntoView = scrollIntoView;

    focusActionError(message);

    expect(document.activeElement).toBe(message);
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
  });
});
