/**
 * Environment helpers for the H5P sidecar.
 *
 * Why:
 *   We need a single source of truth for prod-like detection and feature
 *   gates (e.g. disabling debug HTML pages with `unsafe-inline` CSP).
 */

function _normalize(value) {
  return String(value || "").trim().toLowerCase();
}

export function isProdLikeEnv(gustavEnv) {
  const env = _normalize(gustavEnv);
  return ["prod", "production", "stage", "staging"].includes(env);
}

function _isTruthy(value) {
  return ["1", "true", "yes", "on"].includes(_normalize(value));
}

function _isFalsy(value) {
  return ["0", "false", "no", "off"].includes(_normalize(value));
}

export function debugPagesEnabled({ gustavEnv, enableFlag } = {}) {
  // Defense-in-depth: never allow the debug HTML pages in prod-like envs.
  if (isProdLikeEnv(gustavEnv)) return false;

  // Non-prod: default to enabled (developer convenience).
  if (enableFlag === undefined || enableFlag === null || String(enableFlag).trim() === "") return true;

  if (_isTruthy(enableFlag)) return true;
  if (_isFalsy(enableFlag)) return false;

  // Conservative fallback for unexpected values.
  return false;
}

