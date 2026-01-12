/**
 * Cookie utilities for the H5P sidecar.
 *
 * Why:
 *   The H5P service forwards requests to the main GUSTAV web service for
 *   authentication and authorisation checks. Forwarding the *entire* Cookie
 *   header would unnecessarily expose unrelated cookies to the upstream.
 *
 *   We therefore forward only the single session cookie (`gustav_session` by
 *   default). This is data minimisation and reduces accidental coupling.
 */

export function buildSessionCookieHeader(cookieHeader, cookieName) {
  const header = String(cookieHeader || "");
  const name = String(cookieName || "").trim();
  if (!name) return "";

  // Keep this KISS and preserve the raw cookie value:
  // - do not decode/re-encode (prevents subtle value drift)
  // - return the first matching cookie
  for (const part of header.split(";")) {
    const trimmed = String(part || "").trim();
    if (!trimmed) continue;
    if (!trimmed.startsWith(`${name}=`)) continue;
    const value = trimmed.slice(name.length + 1);
    if (!value) return "";
    return `${name}=${value}`;
  }
  return "";
}

