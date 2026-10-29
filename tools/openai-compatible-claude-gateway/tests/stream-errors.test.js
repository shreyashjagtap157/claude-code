import test from "node:test";
import assert from "node:assert/strict";
import { close, createFakeUpstream, listen, startGateway } from "./helpers.js";

const localAuthorization = { authorization: "Bearer local-gateway-fixture" };
const authConfig = {
  GATEWAY_API_KEY: "local-gateway-fixture",
  OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-test-model":"mapped-model"}',
  OPENAI_COMPATIBLE_CAPABILITIES: '{"streaming":true,"toolCalling":true,"parallelToolCalls":true,"images":true,"jsonSchema":true,"streamUsage":true,"streamRequiresDone":true}'
};
function body(overrides = {}) {
  return { model: "claude-test-model", max_tokens: 128, messages: [{ role: "user", content: "Hello" }], ...overrides };
}
async function createHarness({ mode, config = {}, onStreamClose } = {}) {
  const requests = [];
  const upstream = createFakeUpstream({ requests, mode, onStreamClose });
  const upstreamUrl = await listen(upstream);
  const { gateway, url } = await startGateway(upstreamUrl, { ...authConfig, ...config });
  return { requests, upstream, gateway, url, async cleanup() { await close(gateway); await close(upstream); } };
}
function sendStream(harness, payload = body({ stream: true })) {
  return fetch(harness.url + "/v1/messages", {
    method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(payload)
  });
}

test("simultaneous streamed tool indices preserve IDs and independently assembled JSON arguments", async t => {
  const h = await createHarness({ mode: "normal" }); t.after(h.cleanup);
  const tools = [
    { name: "weather", input_schema: { type: "object", properties: { city: { type: "string" } } } },
    { name: "lookup", input_schema: { type: "object", properties: { term: { type: "string" } } } }
  ];
  const response = await sendStream(h, body({ stream: true, messages: [{ role: "user", content: "stream-multi-tool" }], tools }));
  assert.equal(response.status, 200);
  const raw = await response.text();
  const events = [...raw.matchAll(/event: ([^\n]+)\ndata: ([^\n]+)\n\n/g)].map(m => ({ event: m[1], data: JSON.parse(m[2]) }));
  const starts = events.filter(e => e.event === "content_block_start" && e.data.content_block.type === "tool_use");
  assert.deepEqual(starts.map(e => e.data.content_block.id), ["call_weather", "call_lookup"]);
  const argsFor = index => events.filter(e => e.event === "content_block_delta" && e.data.index === index && e.data.delta.type === "input_json_delta").map(e => e.data.delta.partial_json).join("");
  assert.equal(argsFor(starts[0].data.index), '{"city":"Pune"}');
  assert.equal(argsFor(starts[1].data.index), '{"term":"forecast"}');
  assert.equal(events.find(e => e.event === "message_delta").data.delta.stop_reason, "tool_use");
  assert.equal(events.at(-1).event, "message_stop");
});

test("upstream reset mid-stream yields a terminal Anthropic error instead of false completion", async t => {
  const h = await createHarness({ mode: "stream-reset" }); t.after(h.cleanup);
  const response = await sendStream(h);
  assert.equal(response.status, 200);
  const raw = await response.text();
  assert.match(raw, /event: content_block_delta/);
  assert.match(raw, /event: error/);
  assert.match(raw, /disconnected unexpectedly/);
  assert.equal(raw.includes("event: message_stop"), false);
});

test("stalled upstream stream hits the configured idle timeout and emits a terminal error", async t => {
  const h = await createHarness({ mode: "stream-idle", config: { GATEWAY_STREAM_IDLE_TIMEOUT_MS: "60" } }); t.after(h.cleanup);
  const response = await sendStream(h);
  assert.equal(response.status, 200);
  const raw = await response.text();
  assert.match(raw, /event: error/);
  assert.match(raw, /idle for 60 ms/);
  assert.equal(raw.includes("event: message_stop"), false);
});

test("malformed completed streamed tool arguments fail before a successful message_stop", async t => {
  const h = await createHarness({ mode: "normal" }); t.after(h.cleanup);
  const response = await sendStream(h, body({ stream: true, messages: [{ role: "user", content: "stream-malformed-tool" }], tools: [{ name: "weather", input_schema: { type: "object" } }] }));
  assert.equal(response.status, 200);
  const raw = await response.text();
  assert.match(raw, /event: error/);
  assert.match(raw, /malformed JSON/);
  assert.equal(raw.includes("event: message_stop"), false);
});

test("client cancellation aborts a pending upstream stream", async t => {
  let resolveClosed;
  const upstreamClosed = new Promise(resolve => { resolveClosed = resolve; });
  const h = await createHarness({ mode: "stream-idle", onStreamClose: resolveClosed }); t.after(h.cleanup);
  const controller = new AbortController();
  const response = await fetch(h.url + "/v1/messages", {
    method: "POST", signal: controller.signal,
    headers: { ...localAuthorization, "content-type": "application/json" },
    body: JSON.stringify(body({ stream: true }))
  });
  assert.equal(response.status, 200);
  const reader = response.body.getReader();
  const first = await reader.read();
  assert.ok(new TextDecoder().decode(first.value).includes("message_start"));
  reader.releaseLock();
  controller.abort();
  await Promise.race([upstreamClosed, new Promise((_, reject) => { const timer = setTimeout(() => reject(new Error("Upstream stream was not cancelled after the client disconnected.")), 750); timer.unref?.(); })]);
});

test("malformed JSON and oversized request bodies return typed Anthropic errors", async t => {
  const h = await createHarness({ mode: "normal", config: { GATEWAY_MAX_BODY_BYTES: "256" } }); t.after(h.cleanup);
  const malformed = await fetch(h.url + "/v1/messages", { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: "{not-json" });
  assert.equal(malformed.status, 400);
  assert.equal((await malformed.json()).error.type, "invalid_request_error");
  const oversized = await fetch(h.url + "/v1/messages", { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(body({ messages: [{ role: "user", content: "x".repeat(2000) }] })) });
  assert.equal(oversized.status, 413);
  assert.equal((await oversized.json()).error.type, "request_too_large");
});
