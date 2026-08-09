import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import FieldError from "./FieldError.svelte";

describe("FieldError", () => {
  it("renders a stable description target without creating a second live alert", () => {
    render(FieldError, {
      props: {
        id: "material-title-error",
        message: "Bitte gib einen Titel ein."
      }
    });

    const error = screen.getByText("Bitte gib einen Titel ein.");
    expect(error).toHaveAttribute("id", "material-title-error");
    expect(error).not.toHaveAttribute("role", "alert");
    expect(error).toHaveClass("field-error");
  });
});
