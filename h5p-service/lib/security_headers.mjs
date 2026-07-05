// Default CSP for all `/h5p/*` responses (strict, no wildcards, no unsafe-eval).
//
// In the embedded GUSTAV flow, the browser enforces the app CSP for script
// execution. This H5P-service CSP remains defense-in-depth for standalone pages.
export const CSP_DEFAULT = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "form-action 'self'",
  "frame-ancestors 'self'",
  "script-src 'self'",
  // H5P uses inline styles and style attributes widely. Keep this scoped here.
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self' data: blob:",
  "frame-src 'self' blob:",
  "worker-src 'self' blob:",
].join("; ");


// Scoped CSP exception for standalone debug HTML pages only.
export const CSP_DEBUG_HTML = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "form-action 'self'",
  "frame-ancestors 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self' data: blob:",
  "frame-src 'self' blob:",
  "worker-src 'self' blob:",
].join("; ");


export const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Content-Security-Policy": CSP_DEFAULT,
};


export function applySecurityHeaders(res, overrides = {}) {
  for (const [key, value] of Object.entries({ ...SECURITY_HEADERS, ...overrides })) {
    res.setHeader(key, value);
  }
}
