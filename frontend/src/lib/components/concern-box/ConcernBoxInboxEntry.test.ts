import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ConcernBoxInboxEntry from "./ConcernBoxInboxEntry.svelte";

describe("ConcernBoxInboxEntry", () => {
  it("renders an open entry with formatted metadata and archive action", () => {
    render(ConcernBoxInboxEntry, {
      props: {
        entry: {
          id: "entry-1",
          course_id: "course-1",
          course_title: "Informatik",
          message_text: "Mir gefällt das so alles nicht.",
          anonymous: true,
          student_name: null,
          created_at: "2026-04-06T09:36:22+00:00",
          archived_at: null
        }
      }
    });

    expect(screen.getByText("Informatik")).toBeInTheDocument();
    expect(screen.getByText("Anonym")).toBeInTheDocument();
    expect(screen.getByText("Mir gefällt das so alles nicht.")).toBeInTheDocument();
    expect(screen.getByText("06.04.2026, 11:36")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archivieren" })).toBeInTheDocument();
  });

  it("renders a restore action and named sender for non-anonymous archived entries", () => {
    render(ConcernBoxInboxEntry, {
      props: {
        entry: {
          id: "entry-2",
          course_id: "course-1",
          course_title: "Informatik",
          message_text: "Mehr Beispiele im Unterricht.",
          anonymous: false,
          student_name: "Max Mustermann",
          created_at: "2026-04-06T09:36:22+00:00",
          archived_at: "2026-04-06T10:00:00+00:00"
        }
      }
    });

    expect(screen.getByText("Max Mustermann")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Wiederherstellen" })).toBeInTheDocument();
  });
});
