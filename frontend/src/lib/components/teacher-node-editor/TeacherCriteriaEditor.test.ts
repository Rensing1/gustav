import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import TeacherCriteriaEditor from "./TeacherCriteriaEditor.svelte";

describe("TeacherCriteriaEditor", () => {
  it("starts with one criterion and keeps the list between one and ten entries", async () => {
    render(TeacherCriteriaEditor);
    expect(screen.getAllByLabelText(/^Kriterium \d+$/)).toHaveLength(1);

    for (let index = 1; index < 10; index += 1) {
      await fireEvent.click(screen.getByRole("button", { name: "Kriterium hinzufügen" }));
    }
    expect(screen.getAllByLabelText(/^Kriterium \d+$/)).toHaveLength(10);
    expect(screen.queryByRole("button", { name: "Kriterium hinzufügen" })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Kriterium 10 entfernen" }));
    expect(screen.getAllByLabelText(/^Kriterium \d+$/)).toHaveLength(9);
  });

  it("moves criteria with accessible controls", async () => {
    render(TeacherCriteriaEditor, { props: { initialValues: ["Erstes", "Zweites"] } });
    await fireEvent.click(screen.getByRole("button", { name: "Kriterium 2 nach oben" }));
    expect(screen.getByLabelText("Kriterium 1")).toHaveValue("Zweites");
    expect(screen.getByLabelText("Kriterium 2")).toHaveValue("Erstes");
  });
});
