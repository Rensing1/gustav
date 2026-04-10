import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import BreadcrumbBar from "./BreadcrumbBar.svelte";

describe("BreadcrumbBar", () => {
  it("renders linked ancestors and a non-linked current item", () => {
    render(BreadcrumbBar, {
      props: {
        items: [
          { label: "Lernraum", href: "/learning" },
          { label: "Programmieren mit Scratch", href: "/learning/courses/course-1" },
          { label: "Erste Schritte" }
        ]
      }
    });

    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lernraum" })).toHaveAttribute("href", "/learning");
    expect(screen.getByRole("link", { name: "Programmieren mit Scratch" })).toHaveAttribute(
      "href",
      "/learning/courses/course-1"
    );
    expect(screen.getByText("Erste Schritte")).toHaveAttribute("aria-current", "page");
  });
});
