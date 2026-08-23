import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import LearningCriteriaDetails from "./LearningCriteriaDetails.svelte";

describe("LearningCriteriaDetails", () => {
  it("renders a nested criterion list with lightly marked qualitative levels", async () => {
    render(LearningCriteriaDetails, {
      props: {
        criteria: [
          { criterion: "Argumentkern", score: 2, max_score: 10, explanation_md: "Noch nicht belegt." },
          { criterion: "Begründung", score: 3, max_score: 10 },
          { criterion: "Materialbezug", score: 7, max_score: 10 },
          { criterion: "Einordnung", score: 9, max_score: 10 },
          { criterion: "Offener Wert", explanation_md: "**Manuelle Prüfung** erforderlich." }
        ]
      }
    });

    const disclosureSummary = screen.getByText("Kriterien im Detail").closest("summary");
    expect(disclosureSummary).not.toBeNull();
    await fireEvent.click(disclosureSummary!);

    const disclosure = disclosureSummary?.closest("details");
    expect(disclosure).not.toBeNull();
    expect(within(disclosure as HTMLElement).getByText("5 Kriterien")).toBeInTheDocument();

    const list = within(disclosure as HTMLElement).getByRole("list", { name: "Bewertungskriterien" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
    expect(within(list).getByText("01")).toBeInTheDocument();
    expect(within(list).getByText("05")).toBeInTheDocument();

    expect(within(list).getByText("Mangelhaft")).toHaveClass("learning-criterion__level--mangelhaft");
    expect(within(list).getByText("Ansatzweise")).toHaveClass("learning-criterion__level--ansatzweise");
    expect(within(list).getByText("Gelungen")).toHaveClass("learning-criterion__level--gelungen");
    expect(within(list).getByText("Hervorragend")).toHaveClass("learning-criterion__level--hervorragend");
    expect(within(list).getByText("Ohne Einstufung")).toHaveClass("learning-criterion__level--ohne-einstufung");
    expect(disclosure?.textContent).not.toContain("/10");
    expect(within(list).getByText("Argumentkern").closest("details")).not.toHaveAttribute("open");
    expect(list.querySelectorAll("details[open]")).toHaveLength(0);
    expect(disclosure?.querySelector(".markdown-prose strong")).not.toBeNull();
  });

  it("opens an individual criterion while keeping its level in the summary", async () => {
    render(LearningCriteriaDetails, {
      props: {
        open: true,
        criteria: [
          { criterion: "Argumentkern", score: 3, max_score: 10, explanation_md: "Argument ergänzen." },
          { criterion: "Materialbezug", score: 8, max_score: 10, explanation_md: "Material passend genutzt." }
        ]
      }
    });

    const materialCriterion = screen.getByText("Materialbezug").closest("details");
    expect(materialCriterion).not.toBeNull();
    expect(materialCriterion).not.toHaveAttribute("open");

    await fireEvent.click(within(materialCriterion!).getByText("Materialbezug"));

    expect(materialCriterion).toHaveAttribute("open");
    expect(within(materialCriterion!).getByText("Gelungen")).toBeInTheDocument();
    expect(within(materialCriterion!).getByText("Material passend genutzt.")).toBeInTheDocument();
  });

  it("keeps every criterion closed when no valid score exists", () => {
    render(LearningCriteriaDetails, {
      props: {
        criteria: [{ criterion: "Langes Kriterium ohne Score", explanation_md: "Bitte prüfen." }],
        open: true
      }
    });

    const criterion = screen.getByText("Langes Kriterium ohne Score").closest("details");
    expect(criterion).not.toHaveAttribute("open");
  });
});
