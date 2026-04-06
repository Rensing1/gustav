import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ConcernBoxComposer from "./ConcernBoxComposer.svelte";

describe("ConcernBoxComposer", () => {
  it("renders the shared learner form with an anonymized default", () => {
    render(ConcernBoxComposer, {
      props: {
        courses: [
          { id: "course-1", title: "Informatik" },
          { id: "course-2", title: "Mathematik" }
        ],
        values: {
          courseId: "",
          messageText: "",
          anonymous: true
        },
        sent: false
      }
    });

    expect(screen.getByLabelText("Kurs")).toBeInTheDocument();
    expect(screen.getByLabelText("Beitrag")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Anonym bleiben" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Beitrag senden" })).toBeInTheDocument();
  });

  it("keeps submitted values and shows feedback messages", () => {
    render(ConcernBoxComposer, {
      props: {
        courses: [{ id: "course-1", title: "Informatik" }],
        values: {
          courseId: "course-1",
          messageText: "Mehr Ruhe bitte.",
          anonymous: false
        },
        error: "Bitte präziser schreiben.",
        sent: true
      }
    });

    expect(screen.getByLabelText("Kurs")).toHaveValue("course-1");
    expect(screen.getByLabelText("Beitrag")).toHaveValue("Mehr Ruhe bitte.");
    expect(screen.getByRole("checkbox", { name: "Anonym bleiben" })).not.toBeChecked();
    expect(screen.getByText("Bitte präziser schreiben.")).toBeInTheDocument();
    expect(screen.getByText("Dein Beitrag wurde gesendet.")).toBeInTheDocument();
  });
});
