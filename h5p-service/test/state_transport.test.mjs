import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";

const source = () => readFileSync(new URL("../vendor/webcomponents/overrides/state-transport.js", import.meta.url), "utf8");

function install(sendBeacon) {
  let transport;
  runInNewContext(source(), {
    window: { H5P: { jQuery: { ajaxTransport: (type, factory) => {
      assert.equal(type, "+json"); transport = factory;
    } } }, location: { href: "https://app.localhost/learning", origin: "https://app.localhost" } },
    navigator: { sendBeacon }, URL, Blob
  });
  return transport;
}

test("sync H5P state saves keep their form body, session origin and task context", async () => {
  const sent = [];
  const factory = install((url, data) => { sent.push({ url, data }); return true; });
  const url = "/h5p/contentUserData/42/state/0?contextId=task-1";
  const body = "data=%7B%22answers%22%3A%5B1%5D%7D&preload=1&invalidate=1";
  const transport = factory({ type: "POST", async: false, url, data: body });
  let result;
  transport.send({}, (...args) => { result = args; });
  assert.equal(sent[0].url, "https://app.localhost" + url);
  assert.equal(await sent[0].data.text(), body);
  assert.match(sent[0].data.type, /^application\/x-www-form-urlencoded/);
  assert.equal(result[0], 200);
  assert.deepEqual(JSON.parse(result[2].text), { success: true });
});

test("ordinary Ajax and foreign endpoints retain their original transports", () => {
  const factory = install(() => { assert.fail("unrelated requests must not use Beacon"); });
  const normal = { type: "POST", async: false, url: "/h5p/contentUserData/42/state/0", data: "data=state" };
  for (const options of [
    { ...normal, async: true }, { ...normal, type: "GET" },
    { ...normal, url: "https://foreign.example/h5p/contentUserData/42/state/0" },
    { ...normal, url: "/api/learning/submissions" }
  ]) assert.equal(factory(options), undefined);
  assert.equal(install(undefined), undefined);
});

test("a full Beacon queue or transport exception is not reported as saved", () => {
  for (const send of [() => false, () => { throw new Error("queue unavailable"); }]) {
    const factory = install(send);
    const transport = factory({ type: "POST", async: false, url: "/h5p/contentUserData/42/state/0", data: "data=state" });
    let result;
    transport.send({}, (...args) => { result = args; });
    assert.equal(result[0], 0);
    assert.equal(result[1], "error");
  }
});
