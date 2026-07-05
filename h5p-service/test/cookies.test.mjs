import assert from "node:assert/strict";
import test from "node:test";

import { buildSessionCookieHeader, parseCookies } from "../lib/cookies.mjs";

test("buildSessionCookieHeader: returns empty when header is missing", () => {
  assert.equal(buildSessionCookieHeader("", "gustav_session"), "");
  assert.equal(buildSessionCookieHeader(null, "gustav_session"), "");
  assert.equal(buildSessionCookieHeader(undefined, "gustav_session"), "");
});

test("buildSessionCookieHeader: returns empty when cookieName is missing", () => {
  assert.equal(buildSessionCookieHeader("gustav_session=abc", ""), "");
  assert.equal(buildSessionCookieHeader("gustav_session=abc", "   "), "");
});

test("buildSessionCookieHeader: extracts only the named cookie", () => {
  const out = buildSessionCookieHeader("other=1; gustav_session=abc; third=2", "gustav_session");
  assert.equal(out, "gustav_session=abc");
});

test("buildSessionCookieHeader: preserves raw cookie value (no decode/re-encode drift)", () => {
  const header = "gustav_session=abc%3Ddef%2Fghi; other=1";
  const out = buildSessionCookieHeader(header, "gustav_session");
  assert.equal(out, "gustav_session=abc%3Ddef%2Fghi");
});

test("buildSessionCookieHeader: empty session cookie is treated as missing", () => {
  const out = buildSessionCookieHeader("gustav_session=; other=1", "gustav_session");
  assert.equal(out, "");
});

test("buildSessionCookieHeader: rejects CR/LF in cookie value (header injection defense)", () => {
  const header = "gustav_session=abc\r\ninjected=1; other=1";
  const out = buildSessionCookieHeader(header, "gustav_session");
  assert.equal(out, "");
});

test("buildSessionCookieHeader: rejects LF in cookie value (header injection defense)", () => {
  const header = "other=1; gustav_session=abc\ninjected=1";
  const out = buildSessionCookieHeader(header, "gustav_session");
  assert.equal(out, "");
});

test("parseCookies: returns decoded cookie values by name", () => {
  const parsed = parseCookies("gustav_session=abc%3Ddef; theme=dark; empty=");

  assert.deepEqual(parsed, {
    gustav_session: "abc=def",
    theme: "dark",
    empty: "",
  });
});

test("parseCookies: preserves raw malformed values instead of throwing", () => {
  const parsed = parseCookies("gustav_session=%E0%A4%A; frontend=ok");

  assert.deepEqual(parsed, {
    gustav_session: "%E0%A4%A",
    frontend: "ok",
  });
});

test("parseCookies: ignores empty cookie parts", () => {
  assert.deepEqual(parseCookies(" ; gustav_session=abc; ;"), {
    gustav_session: "abc",
  });
  assert.deepEqual(parseCookies(""), {});
  assert.deepEqual(parseCookies(undefined), {});
});
