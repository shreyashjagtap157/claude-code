import test from "node:test";
import assert from "node:assert/strict";
import { close, createFakeUpstream, listen, startGateway } from "./helpers.js";

async function setup({ mode = "normal", config = {} } = {}) {
  const requests = []; const upstream = createFakeUpstream({ requests, mode }); const upstreamBase = await listen(upstream); const gatewaySetup = await startGateway(upstreamBase, config);
  return { ...gatewaySetup, upstream, requests, async cleanup() { await close(gatewaySetup.gateway); await close(upstream); } };
}
function basicBody(overrides = {}) { return { model: "claude-test-model", max_tokens: 128, messages: [{ role: "user", content: "Hello" }], ...overrides }; }
const localAuthorization = { authorization: "Bearer local-gateway-fixture" };
const authConfig = { GATEWAY_API_KEY: "local-gateway-fixture", OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-test-model":"mapped-model"}', OPENAI_COMPATIBLE_CAPABILITIES: '{"streaming":true,"toolCalling":true,"parallelToolCalls":true,"images":true,"jsonSchema":true,"streamUsage":true,"streamRequiresDone":true}' };

test("HTTP end-to-end request translates Anthropic Messages to Chat Completions and isolates credentials", async t => {
  const state = await setup({ config: authConfig }); t.after(state.cleanup);
  const health = await fetch(`${state.url}/health`); assert.equal(health.status, 200); assert.deepEqual(await health.json(), { status: "ok" });
  const unauthenticated = await fetch(`${state.url}/v1/models`); assert.equal(unauthenticated.status, 401);
  const response = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ system: "Be concise", temperature: 0.1 })) });
  assert.equal(response.status, 200); const body = await response.json(); assert.equal(body.type, "message"); assert.equal(body.model, "claude-test-model"); assert.equal(body.content[0].text, "Hello from the fake upstream."); assert.equal(body.stop_reason, "end_turn"); assert.deepEqual(body.usage, { input_tokens: 10, output_tokens: 6 });
  assert.equal(state.requests.length, 1); assert.equal(state.requests[0].headers.authorization, "Bearer upstream-secret-fixture"); assert.equal(state.requests[0].headers.local, undefined); assert.equal(state.requests[0].body.model, "mapped-model"); assert.equal(state.requests[0].body.messages[0].content, "Be concise"); assert.equal(state.requests[0].body.messages[1].content, "Hello"); assert.equal(JSON.stringify(body).includes("upstream-secret-fixture"), false);
});

test("full multi-turn tool-use/tool-result round trip preserves exact provider tool IDs", async t => {
  const state = await setup({ config: authConfig }); t.after(state.cleanup);
  const tools = [{ name: "weather", description: "Get weather", input_schema: { type: "object", properties: { city: { type: "string" } }, required: ["city"] } }];
  const first = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ messages: [{ role: "user", content: "use a tool" }], tools })) });
  assert.equal(first.status, 200); const firstBody = await first.json(); assert.equal(firstBody.stop_reason, "tool_use"); assert.deepEqual(firstBody.content[0], { type: "tool_use", id: "call_exact_123", name: "weather", input: { city: "Pune" } });
  const second = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ messages: [{ role: "user", content: "use a tool" }, { role: "assistant", content: [{ type: "tool_use", id: "call_exact_123", name: "weather", input: { city: "Pune" } }] }, { role: "user", content: [{ type: "tool_result", tool_use_id: "call_exact_123", content: [{ type: "text", text: "Sunny" }] }] }], tools })) });
  assert.equal(second.status, 200); const secondBody = await second.json(); assert.equal(secondBody.content[0].text, "Tool result received.");
  const secondUpstream = state.requests[1].body; assert.equal(secondUpstream.messages.at(-1).role, "tool"); assert.equal(secondUpstream.messages.at(-1).tool_call_id, "call_exact_123"); assert.equal(secondUpstream.messages.at(-1).content, "Sunny");
});

test("streaming returns incremental Anthropic events and valid final usage/stop events", async t => {
  const state = await setup({ config: authConfig }); t.after(state.cleanup);
  const response = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ stream: true })) });
  assert.equal(response.status, 200); assert.match(response.headers.get("content-type"), /text\/event-stream/); const raw = await response.text();
  const events = [...raw.matchAll(/event: ([^\n]+)\ndata: ([^\n]+)\n\n/g)].map(match => ({ event: match[1], data: JSON.parse(match[2]) }));
  assert.equal(events[0].event, "message_start"); assert.ok(events.some(event => event.event === "content_block_start")); assert.equal(events.filter(event => event.event === "content_block_delta").map(event => event.data.delta.text || "").join(""), "Hello");
  assert.equal(events.at(-2).event, "message_delta"); assert.equal(events.at(-2).data.delta.stop_reason, "end_turn"); assert.equal(events.at(-2).data.usage.input_tokens, 7); assert.equal(events.at(-1).event, "message_stop"); assert.equal(state.requests[0].body.stream_options.include_usage, true);
});

test("streamed fragmented function arguments become a valid Anthropic tool_use block", async t => {
  const state = await setup({ config: authConfig }); t.after(state.cleanup);
  const tools = [{ name: "weather", description: "Get weather", input_schema: { type: "object", properties: { city: { type: "string" } }, required: ["city"] } }];
  const response = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ stream: true, messages: [{ role: "user", content: "stream-tool" }], tools })) });
  assert.equal(response.status, 200); const raw = await response.text(); const events = [...raw.matchAll(/event: ([^\n]+)\ndata: ([^\n]+)\n\n/g)].map(match => ({ event: match[1], data: JSON.parse(match[2]) }));
  const starts = events.filter(event => event.event === "content_block_start"); assert.equal(starts.length, 1); assert.equal(starts[0].data.content_block.type, "tool_use"); assert.equal(starts[0].data.content_block.id, "call_stream_1");
  const toolIndex = starts[0].data.index; const partial = events.filter(event => event.event === "content_block_delta" && event.data.index === toolIndex && event.data.delta.type === "input_json_delta").map(event => event.data.delta.partial_json).join("");
  assert.equal(partial, '{"city":"Pune"}'); assert.equal(events.find(event => event.event === "message_delta").data.delta.stop_reason, "tool_use"); assert.equal(events.at(-1).event, "message_stop"); assert.equal(state.requests[0].body.stream, true); assert.equal(state.requests[0].body.tools[0].function.name, "weather");
});

test("upstream safeguard_results are explicitly rejected rather than silently treated as Anthropic validation", async t => {
  const state = await setup({ mode: "safeguard-results", config: authConfig }); t.after(state.cleanup);
  const response = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody()) });
  assert.equal(response.status, 502); assert.match((await response.json()).error.message, /does not implement or qualify for Anthropic server-side classifier protocol/);
});

test("upstream error body and credentials are not reflected in client errors", async t => {
  const state = await setup({ mode: "http-error", config: authConfig }); t.after(state.cleanup);
  const response = await fetch(`${state.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody()) }); assert.equal(response.status, 502); const text = await response.text();
  assert.match(text, /configured credentials/); assert.equal(text.includes("private detail must not escape"), false); assert.equal(text.includes("upstream-secret-fixture"), false); assert.equal(text.includes("local-gateway-fixture"), false);
});

test("invalid upstream JSON and non-SSE streaming response fail with Anthropic-shaped errors", async t => {
  const jsonState = await setup({ mode: "invalid-json", config: authConfig }); t.after(jsonState.cleanup);
  const badJson = await fetch(`${jsonState.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody()) }); assert.equal(badJson.status, 502); assert.equal((await badJson.json()).error.type, "api_error");
  const streamState = await setup({ mode: "json-stream-response", config: authConfig }); t.after(streamState.cleanup);
  const noSse = await fetch(`${streamState.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ stream: true })) }); assert.equal(noSse.status, 502); assert.match((await noSse.json()).error.message, /did not return Content-Type: text\/event-stream/);
});

test("invalid SSE JSON and missing [DONE] become terminal error events, not corrupted successful messages", async t => {
  const invalid = await setup({ mode: "invalid-sse", config: authConfig }); t.after(invalid.cleanup);
  const invalidResponse = await fetch(`${invalid.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ stream: true })) }); const invalidText = await invalidResponse.text();
  assert.match(invalidText, /event: error/); assert.equal(invalidText.includes("event: message_stop"), false);
  const missing = await setup({ mode: "missing-done", config: authConfig }); t.after(missing.cleanup);
  const missingResponse = await fetch(`${missing.url}/v1/messages`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify(basicBody({ stream: true })) }); const missingText = await missingResponse.text();
  assert.match(missingText, /without the required \[DONE\] marker/); assert.equal(missingText.includes("event: message_stop"), false);
});

test("models discovery fallback and count_tokens remain non-fabricating", async t => {
  const state = await setup({ config: authConfig }); t.after(state.cleanup);
  const models = await fetch(`${state.url}/v1/models`, { headers: localAuthorization }); const body = await models.json(); assert.deepEqual(body.data.map(item => item.id), ["claude-test-model", "fake-model"]);
  const count = await fetch(`${state.url}/v1/messages/count_tokens`, { method: "POST", headers: { ...localAuthorization, "content-type": "application/json" }, body: JSON.stringify({ model: "claude-test-model", messages: [] }) });
  assert.equal(count.status, 404); assert.match((await count.json()).error.message, /character-based estimate/);
});

test("health route is safe and remains available without gateway credentials", async t => {
  const state = await setup({ config: authConfig }); t.after(state.cleanup);
  const response = await fetch(`${state.url}/`); assert.equal(response.status, 200); const body = await response.json(); assert.equal(body.status, "ok"); assert.equal(JSON.stringify(body).includes("fake-model"), false); assert.equal(JSON.stringify(body).includes("upstream-secret-fixture"), false);
});
