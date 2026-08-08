import { render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import Page from "./+page.svelte";
import type { PageData } from "./$types";

function pageData(totalTokens = 1_600, unknownEvents = 2): PageData {
  return {
    theme: "light",
    bootstrap: null,
    appSessionActive: false,
    breadcrumbs: [],
    hidePageHeading: true,
    pageCopy: "Technischer Verbrauch nach Modell und Nutzungsart",
    pageTitle: "KI-Nutzung",
    wideWorkspaceShell: true,
    filterValues: { fromDate: "", toDate: "", unitId: "" },
    units: [{ id: "unit-1", title: "Lineare Funktionen" }],
    usage: {
      course: { id: "course-1", title: "Mathematik 10", href: "/teaching/courses/course-1" },
      totals: {
        input_tokens: totalTokens ? 1_234 : 0,
        output_tokens: totalTokens ? 366 : 0,
        total_tokens: totalTokens,
        known_events: totalTokens ? 3 : 0,
        unknown_events: totalTokens ? unknownEvents : 0,
        breakdown: totalTokens
          ? [
              {
                model: "openai/mistral-small-latest",
                stage: "reply",
                input_tokens: 800,
                output_tokens: 200,
                total_tokens: 1_000
              }
            ]
          : []
      }
    }
  };
}

describe("teacher course AI usage page", () => {
  it("shows course totals and a localized model/activity breakdown without learner rows", () => {
    render(Page, { props: { data: pageData() } });

    expect(screen.getByText("1.234")).toBeInTheDocument();
    expect(screen.getByText("366")).toBeInTheDocument();
    expect(screen.getByText("1.600")).toBeInTheDocument();
    expect(screen.getByText("2 unbekannte Aufrufe")).toBeInTheDocument();

    const table = screen.getByRole("table", { name: "Tokennutzung nach Modell und Nutzungsart" });
    expect(within(table).getAllByRole("columnheader")).toHaveLength(5);
    expect(within(table).getByText("openai/mistral-small-latest")).toBeInTheDocument();
    expect(within(table).getByText("Dialogantwort")).toBeInTheDocument();
    expect(screen.queryByText("Lena Beispiel")).not.toBeInTheDocument();
  });

  it("hides the quiet unknown-usage note when every provider call has telemetry", () => {
    render(Page, { props: { data: pageData(1_600, 0) } });

    expect(screen.queryByText(/unbekannte[r]? Aufrufe?/)).not.toBeInTheDocument();
  });

  it("shows a focused empty state", () => {
    render(Page, { props: { data: pageData(0) } });

    expect(screen.getByText("Für diesen Kurs wurden noch keine LLM-Tokens erfasst.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
