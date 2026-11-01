import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import LearnerTaskContext from "./LearnerTaskContext.svelte";
import type { LearnerMaterialContextModule } from "$lib/learning-unit/workspace";

function props() {
  const modules: LearnerMaterialContextModule[] = [{
    id: "module-1", title: "Grundlagen", current: true, closable: false,
    loaded: true, loading: false, error: null,
    items: [1, 2].map((position) => ({
      key: `material:${position}`, kind: "material", title: `Quelle ${position}`,
      position, moduleId: "module-1", contextLabel: "Grundlagen",
      material: { id: String(position), title: `Quelle ${position}`, kind: "markdown", body_md: `Vollständiger Quellentext ${position}.` }
    }))
  }];
  return {
    courseId: "course-1", taskId: "task-1", taskTitle: "Aufgabe 1",
    taskKind: "Interaktive Aufgabe", instructionMd: "Nutze die Quellen.",
    modules, onToggleMaterial: vi.fn(), onOpenReference: vi.fn()
  };
}

describe("LearnerTaskContext material reading", () => {
  it("starts with every material collapsed inside the existing outline", () => {
    render(LearnerTaskContext, props());
    const outline = screen.getByRole("complementary", { name: "Inhalt" });
    for (const nr of [1, 2]) {
      expect(within(outline).getByRole("button", { name: `Quelle ${nr} Material` })).toHaveAttribute("aria-expanded", "false");
      expect(within(outline).queryByText(`Vollständiger Quellentext ${nr}.`)).toBeNull();
    }
    expect(screen.queryByRole("region", { name: "Materialien zur Aufgabe" })).toBeNull();
  });

  it("toggles first and last materials inline, retaining multiple open documents", async () => {
    const data = props();
    const { rerender } = render(LearnerTaskContext, data);
    const outline = screen.getByRole("complementary", { name: "Inhalt" });
    for (const nr of [1, 2]) {
      await fireEvent.click(within(outline).getByRole("button", { name: `Quelle ${nr} Material` }));
      expect(data.onToggleMaterial).toHaveBeenLastCalledWith("module-1", `material:${nr}`);
    }
    expect(data.onOpenReference).not.toHaveBeenCalled();
    await rerender({ ...data, expandedModuleMaterialKeys: { "module-1": ["material:1", "material:2"] } });
    for (const nr of [1, 2]) {
      const button = within(outline).getByRole("button", { name: `Quelle ${nr} Material` });
      expect(button).toHaveAttribute("aria-expanded", "true");
      const body = document.getElementById(button.getAttribute("aria-controls")!);
      expect(body).toContainElement(within(outline).getByText(`Vollständiger Quellentext ${nr}.`));
    }
    await fireEvent.click(within(outline).getByRole("button", { name: "Quelle 1 Material" }));
    expect(data.onToggleMaterial).toHaveBeenLastCalledWith("module-1", "material:1");
    await rerender({ ...data, expandedModuleMaterialKeys: { "module-1": ["material:2"] } });
    expect(within(outline).queryByText("Vollständiger Quellentext 1.")).toBeNull();
    expect(within(outline).getByText("Vollständiger Quellentext 2.")).toBeVisible();
    await fireEvent.click(within(outline).getByRole("button", { name: "Quelle 2 groß lesen" }));
    expect(data.onOpenReference).toHaveBeenCalledWith("material:2");
  });

  it("shows existing loading, error and empty states without invented material", async () => {
    const data = props();
    const { rerender } = render(LearnerTaskContext, { ...data, modules: [{ ...data.modules[0], items: [], loading: true, loaded: false }] });
    expect(screen.getByText("Inhalte werden geladen …")).toBeVisible();
    await rerender({ ...data, modules: [{ ...data.modules[0], items: [], error: "failed", loaded: false }] });
    expect(screen.getByText("Materialien konnten nicht geladen werden.")).toBeVisible();
    await rerender({ ...data, modules: [{ ...data.modules[0], items: [] }] });
    expect(screen.getByText("Keine Materialien oder eigenen Abgaben.")).toBeVisible();
  });

  it("keeps material from another module at its own position without selecting another view", async () => {
    const data = props();
    data.modules.push({ ...data.modules[0], id: "module-2", title: "Vertiefung", current: false,
      items: [{ ...data.modules[0].items[0], key: "material:3", moduleId: "module-2", title: "Quelle 3",
        material: { id: "3", title: "Quelle 3", kind: "markdown", body_md: "Eine weitere Quelle." } }] });
    const { rerender } = render(LearnerTaskContext, data);
    const outline = screen.getByRole("complementary", { name: "Inhalt" });
    await fireEvent.click(within(outline).getByRole("button", { name: "Vertiefung" }));
    await fireEvent.click(within(outline).getByRole("button", { name: "Quelle 3 Material" }));
    expect(data.onToggleMaterial).toHaveBeenCalledWith("module-2", "material:3");
    await rerender({ ...data, expandedModuleMaterialKeys: { "module-2": ["material:3"] } });
    expect(within(outline).getByText("Eine weitere Quelle.")).toBeVisible();
    expect(within(outline).queryByText("Vollständiger Quellentext 1.")).toBeNull();
    expect(data.onOpenReference).not.toHaveBeenCalled();
  });

  it("uses the existing simulation viewer with an explicit start inside the material row", async () => {
    const data = props();
    data.modules[0].items[0].material = { id: "1", title: "Quelle 1", kind: "simulation", body_md: "Probiere die Simulation.", simulation_url: "/simulation" };
    render(LearnerTaskContext, { ...data, expandedModuleMaterialKeys: { "module-1": ["material:1"] } });
    const outline = screen.getByRole("complementary", { name: "Inhalt" });
    expect(within(outline).getByText("Probiere die Simulation.")).toBeVisible();
    expect(outline.querySelector("iframe")).toBeNull();
    await fireEvent.click(within(outline).getByRole("button", { name: "Simulation starten" }));
    expect(within(outline).getByTitle("Simulation Quelle 1")).toHaveAttribute("sandbox", "allow-scripts");
  });
});
