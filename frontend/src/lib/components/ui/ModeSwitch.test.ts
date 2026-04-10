import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ModeSwitch from "./ModeSwitch.svelte";

describe("ModeSwitch", () => {
  it("marks the active mode and renders sibling links", () => {
    render(ModeSwitch, {
      props: {
        label: "Lerneinheit",
        options: [
          { label: "Übersicht", href: "?mode=overview", current: true },
          { label: "Inhalte", href: "?mode=content", current: false }
        ]
      }
    });

    expect(screen.getByRole("navigation", { name: "Lerneinheit" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Übersicht" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Inhalte" })).toHaveAttribute("href", "?mode=content");
  });
});
