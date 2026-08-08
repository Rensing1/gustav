import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import GraphPhaseBand from "./GraphPhaseBand.svelte";

describe("GraphPhaseBand", () => {
  it("selects the phase explicitly without carrying another graph selection", () => {
    render(GraphPhaseBand, {
      props: {
        id: "phase:phase-1",
        data: {
          kind: "phase",
          kicker: "Phase 1",
          title: "Orientierung",
          meta: "",
          selectHref: "?phase=phase-1"
        }
      } as never
    });

    expect(screen.getByRole("link", { name: "PHASE 01 Orientierung" }))
      .toHaveAttribute("href", "?phase=phase-1");
  });
});
