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
    // Defense-in-depth: never forward a value that contains header control chars.
    // This avoids CR/LF injection into upstream requests.
    if (value.includes("\r") || value.includes("\n")) return "";
    return `${name}=${value}`;
  }
  return "";
}


export function parseCookies(cookieHeader) {
  const out = {};
  if (!cookieHeader) return out;
  for (const part of cookieHeader.split(";")) {
    const [rawKey, ...rawRest] = part.trim().split("=");
    if (!rawKey) continue;
    const rawValue = rawRest.join("=");
    // decodeURIComponent can throw on malformed percent encodings; treat such
    // values as opaque and keep the raw string to avoid a 500.
    let decoded = rawValue;
    try {
      decoded = decodeURIComponent(rawValue);
    } catch {
      decoded = rawValue;
    }
    out[rawKey] = decoded;
  }
  return out;
}
