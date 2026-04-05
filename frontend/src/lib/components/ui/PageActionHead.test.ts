import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import PageActionHead from "./PageActionHead.svelte";

describe("PageActionHead", () => {
  it("renders a back link, title, and supporting copy in one shared page head", () => {
    render(PageActionHead, {
      props: {
        backHref: "/teaching/units",
        backLabel: "Zurück zu Lerneinheiten",
        title: "Programmieren mit Scratch",
        copy: "8 Phasen · 21 Module · dieselbe Graphansicht wie für Lernende"
      }
    });

    expect(screen.getByRole("link", { name: "Zurück zu Lerneinheiten" })).toHaveAttribute("href", "/teaching/units");
    expect(screen.getByRole("heading", { name: "Programmieren mit Scratch" })).toBeInTheDocument();
    expect(screen.getByText("8 Phasen · 21 Module · dieselbe Graphansicht wie für Lernende")).toBeInTheDocument();
  });
});
