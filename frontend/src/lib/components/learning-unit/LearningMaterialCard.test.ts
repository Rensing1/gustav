import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import { readWorkspaceCssBundle } from "$lib/styles/test-css-bundle";

import LearningMaterialCard from "./LearningMaterialCard.svelte";

describe("LearningMaterialCard", () => {
  it("starts, resets and closes simulations only after an explicit action", async () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "simulation-1",
          title: "Sitzverteilung",
          kind: "simulation",
          body_md: "Verändere die **Anzahl der Sitze**.",
          mime_type: "text/html",
          simulation_url: "/api/learning/courses/course/materials/simulation-1/simulation"
        },
        expanded: true
      }
    });

    expect(screen.getByText("Anzahl der Sitze")).toBeInTheDocument();
    expect(document.querySelector(".learning-material-simulation__frame")).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: "Simulation starten" }));
    const firstFrame = document.querySelector(".learning-material-simulation__frame");
    expect(firstFrame).not.toBeNull();
    expect(firstFrame).toHaveAttribute("sandbox", "allow-scripts");
    expect(firstFrame).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(screen.getByRole("link", { name: "Separat öffnen" })).toHaveAttribute("target", "_blank");

    await fireEvent.click(screen.getByRole("button", { name: "Zurücksetzen" }));
    expect(document.querySelector(".learning-material-simulation__frame")).not.toBe(firstFrame);

    await fireEvent.click(screen.getByRole("button", { name: "Simulation schließen" }));
    expect(document.querySelector(".learning-material-simulation__frame")).toBeNull();
  });
  it("renders markdown materials as prose instead of a raw pre block", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-1",
          title: "Einführung",
          kind: "markdown",
          body_md:
            "## Überschrift\n\n**Wichtiger** *Text*<br>mit Umbruch\n\n- Eins\n- Zwei\n\n1. Erster\n2. Zweiter\n\n[Link](https://example.com)\n\n| Name | Wert |\n| --- | --- |\n| Alpha | Beta |"
        },
        expanded: true
      }
    });

    const toggle = screen.getByRole("button", { name: /einführung/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Einführung");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAttribute("aria-controls", "material-body-material-1");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(screen.queryByText("Material")).toBeNull();
    expect(screen.getByRole("heading", { name: "Überschrift" })).toBeInTheDocument();
    expect(screen.getByText("Wichtiger", { exact: false })).toBeInTheDocument();
    expect(document.querySelector("em")).not.toBeNull();
    expect(document.querySelector("br")).not.toBeNull();
    expect(document.querySelector("ul")).not.toBeNull();
    expect(document.querySelector("ol")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Link" })).toHaveAttribute("href", "https://example.com");
    expect(document.querySelector("table")).not.toBeNull();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).toBeNull();
    expect(document.querySelector("pre")).toBeNull();
  });

  it("renders collapsed materials as a compact title row", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-2",
          title: "Sehr langer Materialtitel für die kompakte Zeile",
          kind: "markdown",
          body_md: "Inhalt"
        },
        contextLabel: "Modul Graphen",
        expanded: false
      }
    });

    const toggle = screen.getByRole("button", { name: /sehr langer materialtitel/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("title", "Sehr langer Materialtitel für die kompakte Zeile");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle.querySelector("h4")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle--collapsed")).not.toBeNull();
    expect(screen.queryByText("Modul Graphen")).toBeNull();
    expect(screen.queryByText("Material")).toBeNull();
    expect(document.querySelector(".learning-work-item__toggle-icon svg")).not.toBeNull();
  });

  it("renders an inline image preview for file materials when a preview URL exists", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-3",
          title: "Schaubild",
          kind: "file",
          mime_type: "image/png",
          size_bytes: 2048,
          filename_original: "schaubild.png",
          file_url: "/materials/schaubild.png"
        },
        expanded: true
      }
    });

    expect(screen.getByRole("img", { name: "Materialvorschau" })).toBeInTheDocument();
    expect(screen.queryByText("Datei")).not.toBeInTheDocument();
    expect(screen.queryByText("schaubild.png")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Materialvorschau" })).toHaveAttribute("loading", "lazy");
    expect(screen.getByRole("link", { name: "Separat öffnen" })).toHaveAttribute("target", "_blank");
  });

  it("renders an inline PDF preview for file materials when a preview URL exists", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-4",
          title: "Arbeitsblatt",
          kind: "file",
          mime_type: "application/pdf",
          size_bytes: 4096,
          filename_original: "arbeitsblatt.pdf",
          file_url: "/materials/arbeitsblatt.pdf"
        },
        expanded: true
      }
    });

    expect(document.querySelector(".learning-material-file__frame")).not.toBeNull();
    expect(screen.queryByText("Datei")).not.toBeInTheDocument();
    expect(screen.queryByText("arbeitsblatt.pdf")).not.toBeInTheDocument();
    expect(document.querySelector(".learning-material-file__frame")).toHaveAttribute("loading", "lazy");
    expect(screen.getByRole("link", { name: "Separat öffnen" })).toHaveAttribute("target", "_blank");
  });

  it("keeps material rows compact while leaving markdown content open", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-5",
          title: "Grundlagen",
          kind: "markdown",
          body_md: "Einführung in das Thema."
        },
        expanded: true
      }
    });

    expect(screen.getByRole("button", { name: /grundlagen/i })).toBeInTheDocument();
    expect(screen.getByText("Einführung in das Thema.")).toBeInTheDocument();
    expect(document.querySelector(".learning-work-item__body")).not.toBeNull();
    expect(document.querySelector(".learning-material-card__header-inner")).not.toBeNull();
    expect(document.querySelector(".learning-material-card__body-inner")).not.toBeNull();
  });

  it("aligns material titles and reading content to one left-hand axis", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const css = readWorkspaceCssBundle(path.resolve(currentDir, "../../styles"));
    const designSystemCss = css;

    expect(css).toMatch(
      /\.learning-work-item--material\s*\{[^}]*--learning-material-rail-width:\s*min\(100%,\s*calc\(clamp\(30rem,\s*66vw,\s*46rem\)\s*\*\s*var\(--learning-unit-measure-scale\)\)\);[^}]*background:\s*var\(--color-bg-surface\);[^}]*border:\s*1px solid color-mix\(in srgb,\s*var\(--color-border\) 72%,\s*white 28%\);[^}]*box-shadow:\s*2px 2px 0 color-mix\(in srgb,\s*var\(--color-border\) 10%,\s*transparent 90%\);/s
    );
    expect(css).toMatch(
      /\.learning-unit-pane-grid--split\s+\.learning-work-item--material\s*\{[^}]*--learning-material-rail-width:\s*min\(100%,\s*calc\(clamp\(24rem,\s*88%,\s*34rem\)\s*\*\s*var\(--learning-unit-measure-scale\)\)\);/s
    );
    expect(css).toMatch(
      /\.learning-work-item--material\s+\.learning-work-item__toggle\s*\{[^}]*display:\s*block;[^}]*padding:\s*var\(--space-4\)\s+var\(--space-5\)\s+var\(--space-2\);[^}]*background:\s*var\(--color-bg-surface\);/s
    );
    expect(css).toMatch(
      /\.learning-work-item--material\s+\.learning-work-item__body\s*\{[^}]*padding:\s*0\s+var\(--space-5\)\s+var\(--space-5\);[^}]*background:\s*var\(--color-bg-surface\);/s
    );
    expect(css).toMatch(
      /\.learning-work-item--material\s+\.learning-material-card__header-inner,\s*\.learning-work-item--material\s+\.learning-material-card__body-inner\s*\{[^}]*width:\s*min\(100%,\s*68ch\);[^}]*margin-inline:\s*0;/s
    );
    expect(css).toMatch(
      /\.learning-work-item--material\s+\.learning-work-item__title\s*\{[^}]*font-size:\s*calc\(1\.08rem \* var\(--learning-unit-font-scale\)\);[^}]*font-weight:\s*600;[^}]*line-height:\s*1\.18;/s
    );
    expect(css).not.toMatch(
      /\.learning-work-item--material\s+\.learning-work-item__support\s*\{[^}]*width:\s*min\(100%,\s*calc\(clamp\(/s
    );
    expect(css).not.toMatch(
      /\.learning-unit-pane-grid--split\s+\.learning-work-item--material\s+\.learning-work-item__support\s*\{[^}]*width:\s*min\(100%,\s*calc\(clamp\(/s
    );
    expect(css).not.toMatch(/\.learning-work-item--material\s+\.learning-work-item__body\s*\{[^}]*background:\s*transparent;/s);
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell\s+\.learning-work-item__toggle\s*\{[^}]*padding:\s*0\.45rem 0;/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell\s+\.learning-work-item--material\s+\.learning-work-item__toggle\s*\{[^}]*padding:\s*var\(--space-4\)\s+var\(--space-5\)\s+var\(--space-2\);/s
    );
    expect(designSystemCss).toMatch(
      /\.learning-unit-content-shell\s+\.learning-work-item--material\s+\.learning-work-item__title\s*\{[^}]*font-size:\s*calc\(1\.08rem \* var\(--learning-unit-font-scale\)\);[^}]*font-weight:\s*600;[^}]*line-height:\s*1\.18;/s
    );
  });

  it("uses the same inner rail for material headers and file bodies", () => {
    render(LearningMaterialCard, {
      props: {
        material: {
          id: "material-6",
          title: "Europa-Link",
          kind: "file",
          mime_type: "text/html",
          filename_original: "europa.html",
          file_url: "https://example.com/europa"
        },
        expanded: true
      }
    });

    expect(document.querySelector(".learning-material-card__header-inner")).not.toBeNull();
    expect(document.querySelector(".learning-material-card__body-inner")).not.toBeNull();
    expect(document.querySelector(".learning-material-card__support")).not.toBeNull();
    expect(document.querySelector(".learning-work-item__support")).toBeNull();
  });
});
