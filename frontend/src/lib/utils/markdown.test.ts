import { describe, expect, it } from "vitest";

import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("renders headings, emphasis, lists, links, tables and line breaks for learner markdown", () => {
    const html = renderMarkdown(`# Titel

**Fett** und *kursiv*<br>mit Umbruch

- Punkt eins
- Punkt zwei

1. Erster Punkt
2. Zweiter Punkt

[Link](https://example.com)

| Name | Wert |
| --- | --- |
| Alpha | Beta |`);

    expect(html).toContain("<h1>Titel</h1>");
    expect(html).toContain("<strong>Fett</strong>");
    expect(html).toContain("<em>kursiv</em>");
    expect(html).toContain("<br>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<ol>");
    expect(html).toContain('<a href="https://example.com" target="_blank" rel="noreferrer">Link</a>');
    expect(html).toContain("<table>");
    expect(html).toContain("<thead>");
    expect(html).toContain("<tbody>");
  });

  it("keeps only <br> from raw html and strips other html tags", () => {
    const html = renderMarkdown(`Text<br><div>weg</div><script>alert(1)</script>`);

    expect(html).toContain("<br>");
    expect(html).not.toContain("<div>");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("alert(1)");
  });

  it("rejects unsafe link protocols", () => {
    const html = renderMarkdown(`[Böse](javascript:alert(1))`);

    expect(html).not.toContain("href=\"javascript:alert(1)\"");
    expect(html).toContain("<p>[Böse](javascript:alert(1))</p>");
  });
});
