import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import ChoiceSwitch from "./ChoiceSwitch.svelte";

describe("ChoiceSwitch", () => {
  it("renders one native radio group and reports the selected value", async () => {
    const onValueChange = vi.fn();

    render(ChoiceSwitch, {
      props: {
        legend: "Antwortform",
        name: "answer-mode",
        value: "text",
        options: [
          { value: "text", label: "Text schreiben" },
          { value: "upload", label: "Datei hochladen" }
        ],
        onValueChange
      }
    });

    const group = screen.getByRole("group", { name: "Antwortform" });
    const textChoice = screen.getByRole("radio", { name: "Text schreiben" });
    const uploadChoice = screen.getByRole("radio", { name: "Datei hochladen" });

    expect(group).toBeInTheDocument();
    expect(textChoice).toBeChecked();
    expect(uploadChoice).not.toBeChecked();

    await fireEvent.click(uploadChoice);

    expect(onValueChange).toHaveBeenCalledWith("upload");
  });

  it("exposes disabled choices through the native radio control", () => {
    render(ChoiceSwitch, {
      props: {
        legend: "Darstellung",
        name: "display-mode",
        value: "compact",
        options: [
          { value: "compact", label: "Kompakt" },
          { value: "expanded", label: "Ausführlich", disabled: true }
        ],
        onValueChange: vi.fn()
      }
    });

    expect(screen.getByRole("radio", { name: "Ausführlich" })).toBeDisabled();
  });

  it("keeps the active state quiet, token-based and responsive", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(path.resolve(currentDir, "../../styles/ui-primitives.css"), "utf8");
    const activeRule = css.match(/\.choice-switch__option\[data-current="true"\]\s*\{([^}]*)\}/)?.[1] ?? "";
    const activeMarkerRule = css.match(/\.choice-switch__option\[data-current="true"\] span\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(activeRule).toContain("color: var(--color-text)");
    expect(activeRule).not.toContain("background");
    expect(activeRule).not.toContain("box-shadow");
    expect(activeMarkerRule).toContain("color-mix(in srgb, var(--color-accent) 42%, var(--color-border) 58%)");
    expect(css).toContain("@container (max-width: 30rem)");
    expect(css).toMatch(/\.choice-switch__option input:focus-visible \+ span\s*\{[^}]*outline:/s);
  });
});
