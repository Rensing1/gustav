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
  "strong",
  "table",
  "tbody",
  "td",
  "th",
  "thead",
  "tr",
  "ul"
] as const;

const ALLOWED_ATTR = ["href", "target", "rel"] as const;
const EXPLICIT_BREAK_TOKEN = "GUSTAV_LINE_BREAK_TOKEN";

function normalizeRawHtml(raw: string): string {
  return raw
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<br\s*\/?>/gi, EXPLICIT_BREAK_TOKEN)
    .replace(/<\/?[^>]+>/g, "");
}

export function renderMarkdown(raw: string | null | undefined): string {
  const source = String(raw || "").trim();
  if (!source) {
    return "";
  }

  const rendered = markdown.render(normalizeRawHtml(source)).replaceAll(EXPLICIT_BREAK_TOKEN, "<br>");
  return DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR]
  });
}
