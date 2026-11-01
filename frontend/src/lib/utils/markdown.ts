import DOMPurify from "isomorphic-dompurify";
import MarkdownIt from "markdown-it";
import type { Options as MarkdownItOptions } from "markdown-it/lib/index.mjs";
import type Renderer from "markdown-it/lib/renderer.mjs";
import type Token from "markdown-it/lib/token.mjs";

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
});

// An explicit break is syntax only outside code; Markdown's code rules run first.
markdown.inline.ruler.before("text", "explicit_break", (state, silent) => {
  const match = /^<br\s*\/?>/i.exec(state.src.slice(state.pos));
  if (!match) return false;
  if (!silent) state.push("hardbreak", "br", 0);
  state.pos += match[0].length;
  return true;
});

markdown.validateLink = (url: string): boolean => /^https?:\/\//i.test(url);
const defaultLinkOpen =
  markdown.renderer.rules.link_open ??
  ((tokens: Token[], idx: number, options: MarkdownItOptions, _env: unknown, self: Renderer) =>
    self.renderToken(tokens, idx, options));

markdown.renderer.rules.link_open = (
  tokens: Token[],
  idx: number,
  options: MarkdownItOptions,
  env: unknown,
  self: Renderer
) => {
  tokens[idx]?.attrSet("target", "_blank");
  tokens[idx]?.attrSet("rel", "noreferrer");
  return defaultLinkOpen(tokens, idx, options, env, self);
};

const ALLOWED_TAGS = [
  "a",
  "br",
  "code",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "li",
  "ol",
  "p",
  "pre",
  "strong",
  "table",
  "tbody",
  "td",
  "th",
  "thead",
  "tr",
  "ul"
] as const;

const ALLOWED_ATTR = ["href", "target", "rel", "class"] as const;
export function renderMarkdown(raw: string | null | undefined): string {
  const source = String(raw ?? "");
  if (!source.trim()) {
    return "";
  }

  const rendered = markdown.render(source);
  return DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR]
  });
}

/** Readable noninteractive preview using the same grammar as the full renderer. */
export function markdownPlainText(raw: string | null | undefined): string {
  const tokens = markdown.parse(String(raw ?? ""), {});
  function text(tokens: Token[]): string {
    return tokens.map((token) => {
      if (token.children) return text(token.children);
      if (["text", "code_inline", "code_block", "fence", "image"].includes(token.type)) return token.content;
      if (token.block || ["softbreak", "hardbreak"].includes(token.type)) return " ";
      return "";
    }).join("");
  }
  return text(tokens).replace(/\s+/g, " ").trim();
}

export type MarkdownPart =
  | { kind: "html"; html: string }
  | { kind: "diagram"; index: number; source: string }
  | { kind: "container"; tag: "ul" | "ol" | "li" | "div"; children: MarkdownPart[] };

/** Keep the existing sanitized renderer; expose diagram fences as Svelte parts.
 * Only ancestors containing diagrams need structural rendering, so nested
 * lists retain their semantics without rebuilding Markdown's inline grammar.
 */
export function markdownDocument(raw: string | null | undefined): { parts: MarkdownPart[]; diagrams: string[] } {
  const diagrams: string[] = [];
  const isDiagram = (token: Token) => token.type === "fence" && token.info.trim().split(/\s+/, 1)[0] === "mermaid";
  function parts(tokens: Token[]): MarkdownPart[] {
    const output: MarkdownPart[] = [];
    let buffer: Token[] = [];
    function flush() {
      if (!buffer.length) return;
      output.push({ kind: "html", html: DOMPurify.sanitize(markdown.renderer.render(buffer, markdown.options, {}), {
        ALLOWED_TAGS: [...ALLOWED_TAGS], ALLOWED_ATTR: [...ALLOWED_ATTR]
      }) });
      buffer = [];
    }
    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i];
      if (isDiagram(token)) {
        flush();
        output.push({ kind: "diagram", index: diagrams.length, source: token.content });
        diagrams.push(token.content);
      } else if (token.nesting === 1) {
        let depth = 1, end = i + 1;
        for (; end < tokens.length; end++) {
          depth += tokens[end].nesting;
          if (!depth) break;
        }
        const children = tokens.slice(i + 1, end);
        if (children.some(isDiagram)) {
          flush();
          const tag = ["ul", "ol", "li"].includes(token.tag) ? token.tag as "ul" | "ol" | "li" : "div";
          output.push({ kind: "container", tag, children: parts(children) });
        } else buffer.push(...tokens.slice(i, end + 1));
        i = end;
      } else buffer.push(token);
    }
    flush();
    return output;
  }
  return { parts: parts(markdown.parse(String(raw ?? ""), {})), diagrams };
}
