import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherNodeEditorProperties from "./TeacherNodeEditorProperties.svelte";

describe("TeacherNodeEditorProperties", () => {
  it("renders title settings for sections", () => {
    render(TeacherNodeEditorProperties, {
      props: {
        node: {
          id: "section-1",
          kind: "section",
          title: "Orientierung",
          editor_title: "Orientierung"
        },
        settings: { kind: "section" }
      }
    });

    expect(screen.getByText("Eigenschaften")).toBeInTheDocument();
    expect(screen.getByLabelText("Titel")).toHaveValue("Orientierung");
    expect(screen.queryByLabelText("Freischaltung")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eigenschaften speichern" })).toBeInTheDocument();
  });

  it("renders module unlock settings", () => {
    render(TeacherNodeEditorProperties, {
      props: {
        node: {
          id: "module-1",
          kind: "module",
          title: "Krisenjahre",
          editor_title: "Krisenjahre"
        },
        settings: { kind: "module", required_prereq_count: 2 }
      }
    });

    expect(screen.getByLabelText("Titel")).toHaveValue("Krisenjahre");
    expect(screen.getByLabelText("Freischaltung")).toHaveValue(2);
  });
});
