import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import ThemeToggle from "./ThemeToggle.svelte";

describe("ThemeToggle", () => {
  it("renders an icon-only button that announces the dark-mode target state", async () => {
    const onToggle = vi.fn();

    render(ThemeToggle, {
      props: {
        currentTheme: "light",
        onToggle
      }
    });

    const button = screen.getByRole("button", { name: "Dark Mode aktivieren" });
    expect(button).toHaveAttribute("title", "Dark Mode aktivieren");

    await fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("announces the light-mode target state when dark mode is active", () => {
    render(ThemeToggle, {
      props: {
        currentTheme: "dark",
        onToggle: vi.fn()
      }
    });

    expect(screen.getByRole("button", { name: "Light Mode aktivieren" })).toBeInTheDocument();
  });
});
