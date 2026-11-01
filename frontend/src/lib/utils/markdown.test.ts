import { describe, expect, it } from "vitest";

import { markdownPlainText, renderMarkdown } from "./markdown";

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

  it("displays raw HTML as inert text and supports explicit breaks", () => {
    const html = renderMarkdown(`Text<br><div>weg</div><script>alert(1)</script>`);

    expect(html).toContain("<br>");
    expect(html).not.toContain("<div>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  it("rejects unsafe link protocols", () => {
    const html = renderMarkdown(`[Böse](javascript:alert(1))`);

    expect(html).not.toContain("href=\"javascript:alert(1)\"");
    expect(html).toContain("<p>[Böse](javascript:alert(1))</p>");
  });
});


describe("code content integrity", () => {
  it.each([
    "<div>example</div>\n\t<script>alert(1)</script>\n\n  <br>\nGUSTAV_LINE_BREAK_TOKEN\n",
    "if x < 3:\n    print(\"ÄÖÜ\")\n\n\tfinish()\n"
  ])("preserves fenced code exactly as inert text", (code) => {
    const host = document.createElement("div");
    host.innerHTML = renderMarkdown("```html\n" + code + "```");
    expect(host.querySelector("pre > code")?.textContent).toBe(code);
    expect(host.querySelector("script, div, br")).toBeNull();
  });

  it("keeps initial indentation and inline HTML examples", () => {
    const host = document.createElement("div");
    host.innerHTML = renderMarkdown("    first\n      second\n");
    expect(host.querySelector("pre code")?.textContent).toBe("first\n  second\n");
    host.innerHTML = renderMarkdown("`<br>` and `<script>x</script>` and `GUSTAV_LINE_BREAK_TOKEN`");
    expect([...host.querySelectorAll("code")].map((node) => node.textContent)).toEqual([
      "<br>", "<script>x</script>", "GUSTAV_LINE_BREAK_TOKEN"
    ]);
    expect(markdownPlainText("`<br>` outside<br>next")).toBe("<br> outside next");
  });
});

it("splits explicit diagrams while preserving surrounding and nested Markdown", async () => {
  const { markdownDocument } = await import("./markdown");
  const doc = markdownDocument("Vorher\n\n- Text\n\n  ```mermaid\n  flowchart LR\n  A-->B\n  ```\n\nNachher");
  expect(doc.diagrams).toEqual(["flowchart LR\nA-->B\n"]);
  expect(doc.parts.some((part) => part.kind === "container" && part.tag === "ul")).toBe(true);
  expect(JSON.stringify(doc.parts)).toContain("Nachher");
});
