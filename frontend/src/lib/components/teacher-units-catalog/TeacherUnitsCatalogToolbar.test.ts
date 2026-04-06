import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherUnitsCatalogToolbar from "./TeacherUnitsCatalogToolbar.svelte";

describe("TeacherUnitsCatalogToolbar", () => {
  it("renders search and sort controls without a view switch", () => {
    render(TeacherUnitsCatalogToolbar, {
      props: {
        query: "Europa",
        sort: "updated_desc"
      }
    });

    expect(screen.getByRole("searchbox", { name: "Suche" })).toHaveValue("Europa");
    expect(screen.getByRole("combobox", { name: "Sortierung" })).toHaveValue("updated_desc");
    expect(screen.getByRole("button", { name: "Suchen" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Katalogansichten" })).not.toBeInTheDocument();
  });
});
