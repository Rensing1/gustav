import assert from "node:assert/strict";
import { once } from "node:events";
import { readFileSync } from "node:fs";
import test from "node:test";
import express from "express";
import { mountAuthoringRoutes } from "../routes/authoring.mjs";
import { mountPlayerRoutes } from "../routes/player.mjs";
import { mountAjaxRoutes } from "../routes/ajax.mjs";

async function withServer(mount, dependencies, run) {
  const app = express();
  app.use(express.json());
  app.use((req, _res, next) => {
    req.gustavMe = { roles: [req.get("x-role") || "student"] };
    req.user = { id: "subject" };
    next();
  });
  mount(app, dependencies);
  app.use((err, _req, res, _next) => res.status(500).json({ error: "caught" }));
  const server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    await run((url, options = {}) => fetch(base + url, {
      ...options, headers: { "content-type": "application/json", origin: base, ...options.headers },
    }), base);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

const pass = (_req, _res, next) => next();

test("the production image includes all composed routes", () => {
  assert.match(readFileSync("Dockerfile", "utf8"), /COPY routes \/app\/routes/);
});

test("authoring keeps role and CSRF checks ahead of mutation", async () => {
  const calls = [];
  await withServer(mountAuthoringRoutes, {
    h5pEditor: { saveOrUpdateContentReturnMetaData: async (...args) => {
      calls.push(args); return { id: "content", metadata: {} };
    } },
    contentStorage: {}, storageDirs: {}, listInstalledLibraries: async () => [],
    uploadImport: { single: () => pass }, requireDebugHtmlEnabled: pass,
  }, async (request) => {
    const body = JSON.stringify({ library: "H5P.Test 1.0", params: { params: {}, metadata: {} } });
    assert.equal((await request("/contents", { method: "POST", body })).status, 403);
    assert.equal((await request("/contents", { method: "POST", body, headers: { "x-role": "teacher", origin: "https://evil.example" } })).status, 403);
    assert.equal(calls.length, 0);
    const response = await request("/contents", { method: "POST", body, headers: { "x-role": "teacher" } });
    assert.equal(response.status, 201);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    assert.equal((await response.json()).content_id, "content");
    assert.equal(calls.length, 1);
  });
});

test("player fails closed before rendering and preserves scoped finished URL", async () => {
  let renders = 0;
  await withServer(mountPlayerRoutes, {
    h5pPlayer: { render: async () => {
      renders += 1;
      return { integration: { ajax: { setFinished: "/h5p/finishedData" } }, styles: [] };
    } },
    requireDebugHtmlEnabled: pass, reviewTokenSecret: "test-secret",
    sessionCookieName: "session", frontendSessionCookieName: "bff",
    h5pContentAccessCache: new Map(), authCacheTtlSeconds: 30, H5P_AUTH_CACHE_MAX_ENTRIES: 10,
    authForwardingOptions: {}, checkLearningH5PContentAccess: async () => ({ ok: false, status: 404 }),
  }, async (request) => {
    assert.equal((await request("/player/model?content_id=1")).status, 403);
    assert.equal((await request("/player/model?content_id=1&course_id=course")).status, 404);
    assert.equal(renders, 0);
    const response = await request("/player/model?content_id=1&course_id=course&task_id=task", { headers: { "x-role": "teacher" } });
    assert.equal(response.status, 200);
    const model = await response.json();
    assert.equal(model.integration.ajax.setFinished, "/h5p/finishedData?course_id=course&task_id=task");
    assert.equal(renders, 1);
  });
});

test("Ajax guards writes and finished-data override precedes Lumi fallback", async () => {
  const calls = [];
  await withServer(mountAjaxRoutes, {
    h5pAjax: { postAjax: async () => { calls.push("ajax"); return { ok: true }; } },
    h5pEditor: { contentUserDataManager: { setFinished: async () => calls.push("finished") } },
    maybeParseAjaxFiles: pass,
    h5pAjaxExpressRouter: () => (_req, res) => res.status(418).end(),
    sessionCookieName: "session", frontendSessionCookieName: "bff",
    gustavWebInternalBase: "http://web:8000", gustavFrontendInternalBase: "http://gustav-frontend:3000",
    upstreamFetchTimeoutMs: 100, finishedForwardingMetrics: {},
  }, async (request) => {
    assert.equal((await request("/ajax?action=files", { method: "POST", body: "{}" })).status, 403);
    assert.equal(calls.length, 0);
    const translated = await request("/ajax?action=translations", { method: "POST", body: "{}" });
    assert.equal(translated.status, 200);
    assert.equal(translated.headers.get("vary"), "Origin");
    const completed = await request("/finishedData", { method: "POST", body: JSON.stringify({ contentId: "1", score: 1, maxScore: 1 }) });
    assert.equal(completed.status, 200);
    assert.deepEqual(await completed.json(), { success: true });
    assert.deepEqual(calls, ["ajax", "finished"]);
    assert.equal((await request("/fallback")).status, 418);
  });
});

test("finished data persists before forwarding with stable idempotency and minimal cookies", async () => {
  const calls = [];
  const received = [];
  await withServer((app) => {
    app.post("/api/learning/courses/course/tasks/task/submissions", (req, res) => {
      calls.push("forwarded");
      received.push({ body: req.body, cookie: req.get("cookie"), key: req.get("idempotency-key") });
      res.status(201).json({ id: "submission" });
    });
  }, {}, async (_request, backendBase) => {
    await withServer(mountAjaxRoutes, {
      h5pAjax: {},
      h5pEditor: { contentUserDataManager: { setFinished: async () => calls.push("persisted") } },
      maybeParseAjaxFiles: pass, h5pAjaxExpressRouter: () => pass,
      sessionCookieName: "session", frontendSessionCookieName: "bff",
      gustavWebInternalBase: backendBase, gustavFrontendInternalBase: backendBase,
      upstreamFetchTimeoutMs: 1000, finishedForwardingMetrics: { failureTotal: 0 },
    }, async (request) => {
      const body = JSON.stringify({ contentId: "1", score: 2, maxScore: 3, opened: 10, finished: 20 });
      for (let attempt = 0; attempt < 2; attempt += 1) {
        const response = await request("/finishedData?course_id=course&task_id=task", {
          method: "POST", body, headers: { cookie: "session=test-session; unrelated=private" },
        });
        assert.equal(response.status, 200);
      }
    });
  });
  assert.deepEqual(calls, ["persisted", "forwarded", "persisted", "forwarded"]);
  assert.deepEqual(received.map((item) => item.body), [
    { kind: "h5p", score_raw: 2, score_max: 3 }, { kind: "h5p", score_raw: 2, score_max: 3 },
  ]);
  assert.ok(received.every((item) => item.cookie === "session=test-session"));
  assert.match(received[0].key, /^[A-Za-z0-9_-]{1,64}$/);
  assert.equal(received[0].key, received[1].key);
});
