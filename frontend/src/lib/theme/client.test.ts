import { describe, expect, it } from "vitest";

import { syncDocumentTheme } from "./client";

describe("syncDocumentTheme", () => {
  it("writes the active theme to the root html element", () => {
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.colorScheme = "";

    syncDocumentTheme(document, "dark");

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("switches the root element back to light", () => {
    document.documentElement.dataset.theme = "dark";
    document.documentElement.style.colorScheme = "dark";

    syncDocumentTheme(document, "light");

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });
});
