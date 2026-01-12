import test from "node:test";
import assert from "node:assert/strict";

import { debugPagesEnabled } from "../lib/env.mjs";


test("debugPagesEnabled: disabled in prod-like envs (even with opt-in)", () => {
  assert.equal(debugPagesEnabled({ gustavEnv: "prod", enableFlag: "true" }), false);
  assert.equal(debugPagesEnabled({ gustavEnv: "production", enableFlag: "true" }), false);
  assert.equal(debugPagesEnabled({ gustavEnv: "stage" }), false);
  assert.equal(debugPagesEnabled({ gustavEnv: "staging" }), false);
});


test("debugPagesEnabled: enabled by default in dev", () => {
  assert.equal(debugPagesEnabled({ gustavEnv: "dev" }), true);
  assert.equal(debugPagesEnabled({ gustavEnv: "test" }), true);
});


test("debugPagesEnabled: can be disabled via H5P_ENABLE_DEBUG_PAGES=false", () => {
  assert.equal(debugPagesEnabled({ gustavEnv: "dev", enableFlag: "false" }), false);
  assert.equal(debugPagesEnabled({ gustavEnv: "dev", enableFlag: "0" }), false);
  assert.equal(debugPagesEnabled({ gustavEnv: "dev", enableFlag: "off" }), false);
});

