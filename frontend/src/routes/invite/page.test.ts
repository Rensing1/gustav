import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import Page from "./+page.svelte";

describe("public course invitation page", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("moves the fragment into the HttpOnly intent flow before showing minimal preview", async () => {
    history.replaceState({}, "", "/invite#v1.private-capability-token");
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      course_title: "Informatik 9a",
      expires_at: "2026-08-16T12:00:00+00:00"
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    render(Page);
    await screen.findByRole("heading", { name: "Informatik 9a" });

    expect(location.hash).toBe("");
    expect(fetchMock).toHaveBeenCalledWith("/invite/intent", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ token: "v1.private-capability-token" })
    }));
    expect(screen.queryByText(/Lehrkraft/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrieren und beitreten" })).toHaveAttribute("type", "button");
    expect(screen.getByRole("button", { name: "Anmelden und beitreten" })).toBeInTheDocument();
  });

  it("shows one generic result when the capability is invalid", async () => {
    history.replaceState({}, "", "/invite#v1.invalid-capability-token");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
    render(Page);
    await waitFor(() => expect(screen.getByRole("heading", {
      name: "Diese Einladung ist nicht mehr gültig"
    })).toBeInTheDocument());
  });
});
