import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import AuthFrame from "./AuthFrame.svelte";

describe("AuthFrame", () => {
  it("renders a reduced product shell for auth-facing content", () => {
    render(AuthFrame, {
      props: {
        eyebrow: "Session beendet",
        title: "Erfolgreich abgemeldet",
        body: "Du wurdest von GUSTAV abgemeldet.",
        actionHref: "/auth/login",
        actionLabel: "Erneut anmelden"
      }
    });

    expect(screen.getByText("Session beendet")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Erfolgreich abgemeldet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Erneut anmelden" })).toHaveAttribute("href", "/auth/login");
  });
});
