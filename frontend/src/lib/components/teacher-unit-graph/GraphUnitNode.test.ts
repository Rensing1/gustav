import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import GraphUnitNode from "./GraphUnitNode.svelte";

describe("GraphUnitNode", () => {
  it("makes the module copy an explicit selection link", () => {
    render(GraphUnitNode, {
      props: {
        id: "module-1",
        data: {
          kind: "module",
          kicker: "Modul 01",
          title: "Startmodul",
          meta: "1 Material · 1 Aufgabe",
          selectHref: "?module=module-1",
          connectable: false
        }
      } as never
    });

    expect(screen.getByRole("link", { name: "Modul 01 Startmodul 1 Material · 1 Aufgabe" }))
      .toHaveAttribute("href", "?module=module-1");
  });
});
