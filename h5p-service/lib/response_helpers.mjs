import { applySecurityHeaders } from "./security_headers.mjs";


export function sendJson(res, statusCode, body, headers = {}) {
  res.status(statusCode);
  applySecurityHeaders(res);
  res.setHeader("Cache-Control", "private, no-store");
  for (const [name, value] of Object.entries(headers)) res.setHeader(name, value);
  res.json(body);
}


export function sendHtml(res, statusCode, html, headers = {}) {
  res.status(statusCode);
  applySecurityHeaders(res);
  res.setHeader("Cache-Control", "private, no-store");
  for (const [name, value] of Object.entries(headers)) res.setHeader(name, value);
  res.type("html").send(html);
}
