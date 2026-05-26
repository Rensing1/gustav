import { timingSafeEqual } from "node:crypto";

export function safeHeaderValue(value) {
  return String(value || "").replace(/[\r\n]/g, "").trim();
}

export function secretMatches(provided, expected) {
  if (!provided || !expected) return false;
  const providedBytes = Buffer.from(String(provided), "utf-8");
  const expectedBytes = Buffer.from(String(expected), "utf-8");
  if (providedBytes.length !== expectedBytes.length) return false;
  return timingSafeEqual(providedBytes, expectedBytes);
}

export function authenticateInternalTeacher(req, sharedSecret) {
  const providedSecret = req.get("x-gustav-h5p-internal-secret") || "";
  if (!secretMatches(providedSecret, sharedSecret)) return false;

  const sub = safeHeaderValue(req.get("x-gustav-user-sub"));
  const roles = safeHeaderValue(req.get("x-gustav-user-roles"))
    .split(",")
    .map((role) => role.trim())
    .filter(Boolean);
  if (!sub || !roles.length) return false;

  const name = safeHeaderValue(req.get("x-gustav-user-name")) || sub;
  req.gustavInternalAuth = true;
  req.gustavMe = { sub, name, roles };
  req.user = {
    id: sub,
    name,
    email: `${sub}@local.invalid`,
    type: "local",
  };
  req.language = "en";
  return true;
}

export function isInternalAuth(req) {
  return req?.gustavInternalAuth === true;
}

export function rolesAllowTeacher(roles) {
  if (!Array.isArray(roles)) return false;
  return roles.includes("admin") || roles.includes("teacher");
}

export function rolesAllowAdmin(roles) {
  if (!Array.isArray(roles)) return false;
  return roles.includes("admin");
}

export function rolesAllowStudentOrTeacher(roles) {
  if (!Array.isArray(roles)) return false;
  return roles.includes("admin") || roles.includes("teacher") || roles.includes("student");
}
