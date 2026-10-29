import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.js";
import { translateAnthropicRequest } from "../src/translate/request.js";
import { translateChatCompletionResponse, mapFinishReason } from "../src/translate/response.js";
import { GatewayError, UpstreamProtocolError } from "../src/errors.js";

const baseEnv = { OPENAI_COMPATIBLE_BASE_URL: "http://127.0.0.1:8000/v1", OPENAI_COMPATIBLE_MODEL: "test-upstream-model", OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-test":"mapped-model"}', OPENAI_COMPATIBLE_CAPABILITIES: JSON.stringify({ toolCalling: true, parallelToolCalls: true, images: true, jsonSchema: true, reasoningEffort: true }) };
const cfg = loadConfig({ env: baseEnv, cwd: "/no-env" });
function request(overrides = {}) { return { model: "claude-test", max_tokens: 500, system: [{ type: "text", text: "System instructions" }], messages: [{ role: "user", content: [{ type: "text", text: "Hi" }] }], ...overrides }; }

test("translates system, ordered messages and common sampling fields", () => {
  const result = translateAnthropicRequest(request({ messages: [{ role: "user", content: "first" }, { role: "assistant", content: [{ type: "text", text: "second" }] }, { role: "user", content: "third" }], temperature: 0.2, top_p: 0.8, stop_sequences: ["END"] }), cfg);
  assert.equal(result.upstreamModel, "mapped-model"); assert.equal(result.clientModel, "claude-test"); assert.deepEqual(result.request.messages.map(item => item.role), ["system", "user", "assistant", "user"]); assert.equal(result.request.messages[0].content, "System instructions");
  assert.equal(result.request.max_tokens, 500); assert.equal(result.request.temperature, 0.2); assert.equal(result.request.top_p, 0.8); assert.deepEqual(result.request.stop, ["END"]); assert.equal(result.request.stream, false);
});

test("maps system-role entries inside messages to ordered Chat Completions system messages", () => {
  const result = translateAnthropicRequest(request({
    system: "Top-level system",
    messages: [
      { role: "user", content: "first" },
      { role: "system", content: [{ type: "text", text: "In-turn system" }] },
      { role: "assistant", content: "second" },
      { role: "user", content: "third" }
    ]
  }), cfg);
  assert.deepEqual(result.request.messages.map(item => item.role), ["system", "user", "system", "assistant", "user"]);
  assert.deepEqual(result.request.messages.map(item => item.content), ["Top-level system", "first", "In-turn system", "second", "third"]);
});

test("maps system-role message strings and rejects unsupported blocks inside them", () => {
  const result = translateAnthropicRequest(request({
    messages: [{ role: "system", content: "Additional system instruction" }, { role: "user", content: "go" }]
  }), cfg);
  assert.deepEqual(result.request.messages.map(item => item.role), ["system", "system", "user"]);
  assert.equal(result.request.messages[1].content, "Additional system instruction");
  assert.throws(() => translateAnthropicRequest(request({
    messages: [{ role: "system", content: [{ type: "image", source: { type: "url", url: "https://example.com/image.png" } }] }]
  }), cfg), /only text blocks are supported here/);
});

test("translates base64 and remote images only when configured for vision", () => {
  const imageRequest = request({ messages: [{ role: "user", content: [{ type: "text", text: "look" }, { type: "image", source: { type: "base64", media_type: "image/png", data: "aGVsbG8=" } }, { type: "image", source: { type: "url", url: "https://images.example/test.png" } }] }] });
  const result = translateAnthropicRequest(imageRequest, cfg); assert.deepEqual(result.request.messages[1].content[1], { type: "image_url", image_url: { url: "data:image/png;base64,aGVsbG8=" } }); assert.equal(result.request.messages[1].content[2].image_url.url, "https://images.example/test.png");
  const noImages = loadConfig({ env: { ...baseEnv, OPENAI_COMPATIBLE_CAPABILITIES: '{"toolCalling":true}' }, cwd: "/no-env" }); assert.throws(() => translateAnthropicRequest(imageRequest, noImages), /images are disabled/);
  assert.throws(() => translateAnthropicRequest(request({ messages: [{ role: "user", content: [{ type: "image", source: { type: "url", url: "file:///secret" } }] }] }), cfg), /must use HTTP\(S\)/);
});

test("tool definitions and tool_choice modes map to OpenAI function tools", () => {
  const tools = [{ name: "weather", description: "Check weather", input_schema: { type: "object", properties: { city: { type: "string" } }, required: ["city"] } }];
  const result = translateAnthropicRequest(request({ tools, tool_choice: { type: "tool", name: "weather" }, disable_parallel_tool_use: true }), cfg);
  assert.deepEqual(result.request.tools[0], { type: "function", function: { name: "weather", description: "Check weather", parameters: tools[0].input_schema } }); assert.deepEqual(result.request.tool_choice, { type: "function", function: { name: "weather" } }); assert.equal(result.request.parallel_tool_calls, false);
  assert.equal(translateAnthropicRequest(request({ tools, tool_choice: { type: "any" } }), cfg).request.tool_choice, "required"); assert.equal(translateAnthropicRequest(request({ tools, tool_choice: { type: "auto" } }), cfg).request.tool_choice, "auto"); assert.equal(translateAnthropicRequest(request({ tools, tool_choice: { type: "none" } }), cfg).request.tool_choice, "none");
});

test("tool_use and tool_result round-trip with exact IDs across turns", () => {
  const assistant = request({ messages: [{ role: "assistant", content: [{ type: "text", text: "Checking." }, { type: "tool_use", id: "call_exact_123", name: "weather", input: { city: "Pune" } }] }] }); const translated = translateAnthropicRequest(assistant, cfg).request;
  assert.equal(translated.messages[1].content, "Checking."); assert.equal(translated.messages[1].tool_calls[0].id, "call_exact_123"); assert.equal(translated.messages[1].tool_calls[0].function.arguments, '{"city":"Pune"}');
  const followup = request({ system: undefined, messages: [{ role: "user", content: [{ type: "tool_result", tool_use_id: "call_exact_123", content: [{ type: "text", text: "Sunny" }] }] }] }); const mapped = translateAnthropicRequest(followup, cfg).request;
  assert.deepEqual(mapped.messages, [{ role: "tool", tool_call_id: "call_exact_123", content: "Sunny" }]);
});

test("rejects unrepresentable fields, blocks, malformed schemas and unsupported capabilities", () => {
  assert.throws(() => translateAnthropicRequest(request({ extra_mystery: true }), cfg), /Unsupported Anthropic Messages field/); assert.throws(() => translateAnthropicRequest(request({ messages: [{ role: "user", content: [{ type: "audio", source: {} }] }] }), cfg), /unsupported Anthropic content block \"audio\"/);
  assert.throws(() => translateAnthropicRequest(request({ thinking: { type: "enabled", budget_tokens: 10 } }), cfg), /extended thinking cannot be mapped/); assert.throws(() => translateAnthropicRequest(request({ tools: [{ name: "bad name", input_schema: { type: "object" } }] }), cfg), /valid function name/);
  const noTools = loadConfig({ env: { ...baseEnv, OPENAI_COMPATIBLE_CAPABILITIES: "{}" }, cwd: "/no-env" }); assert.throws(() => translateAnthropicRequest(request({ tools: [{ name: "x", input_schema: { type: "object" } }] }), noTools), /tool-capable/);
  assert.throws(() => translateAnthropicRequest(request({ output_config: { format: { type: "json_schema", schema: { type: "object" } } } }), noTools), /Structured JSON output is disabled/); assert.throws(() => translateAnthropicRequest(request({ max_tokens: 0 }), cfg), GatewayError);
});

test("maps structured JSON schema only when configured as supported", () => {
  const result = translateAnthropicRequest(request({ output_config: { format: { type: "json_schema", schema: { type: "object", properties: { ok: { type: "boolean" } } } } } }), cfg);
  assert.equal(result.request.response_format.type, "json_schema"); assert.equal(result.request.response_format.json_schema.strict, true);
});

test("converts non-streaming text, tools, stop reasons and usage", () => {
  const message = translateChatCompletionResponse({ id: "chatcmpl_1", choices: [{ index: 0, message: { role: "assistant", content: "Hello", tool_calls: [{ id: "call_1", type: "function", function: { name: "weather", arguments: '{"city":"Pune"}' } }] }, finish_reason: "tool_calls" }], usage: { prompt_tokens: 11, completion_tokens: 3 } }, "claude-test");
  assert.equal(message.model, "claude-test"); assert.equal(message.content[0].text, "Hello"); assert.deepEqual(message.content[1], { type: "tool_use", id: "call_1", name: "weather", input: { city: "Pune" } }); assert.equal(message.stop_reason, "tool_use"); assert.deepEqual(message.usage, { input_tokens: 11, output_tokens: 3 });
  const maxTokens = translateChatCompletionResponse({ choices: [{ message: { content: "x" }, finish_reason: "length" }] }, "claude-test"); assert.equal(maxTokens.stop_reason, "max_tokens"); assert.deepEqual(maxTokens.usage, { input_tokens: 0, output_tokens: 0 });
  assert.throws(() => translateChatCompletionResponse({ choices: [{ message: { tool_calls: [{ id: "call_2", function: { name: "f", arguments: "not-json" } }] } }] }, "claude-test"), UpstreamProtocolError);
});


test("unsupported message roles are rejected with a safe role-only diagnostic", () => {
  assert.throws(() => translateAnthropicRequest(request({ messages: [{ role: "developer", content: "not an Anthropic Messages role" }] }), cfg), /messages\[0\]\.role "developer" is not supported/);
  assert.throws(() => translateAnthropicRequest(request({ messages: [{ content: "missing role" }] }), cfg), /messages\[0\]\.role undefined is not supported/);
});


test("translator negotiates vision capability independently for model aliases", () => {
  const perModel = loadConfig({ cwd: "/no-env", env: {
    OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1",
    OPENAI_COMPATIBLE_MODEL: "fallback-model",
    OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-vision":"vision-model","claude-text":"text-model"}',
    OPENAI_COMPATIBLE_CAPABILITIES: '{"images":false,"toolCalling":false}',
    OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '{"vision-model":{"images":true},"claude-vision":{"toolCalling":true}}'
  }});
  const imageRequest = request({ model: "claude-vision", messages: [{ role: "user", content: [{ type: "image", source: { type: "base64", media_type: "image/png", data: "aGVsbG8=" } }] }] });
  const vision = translateAnthropicRequest(imageRequest, perModel);
  assert.equal(vision.upstreamModel, "vision-model");
  assert.equal(vision.capabilities.images, true);
  assert.equal(vision.capabilities.toolCalling, true);
  const textRequest = request({ model: "claude-text", messages: [{ role: "user", content: [{ type: "image", source: { type: "base64", media_type: "image/png", data: "aGVsbG8=" } }] }] });
  assert.throws(() => translateAnthropicRequest(textRequest, perModel), /images are disabled/);
});


test("finish reasons are mapped explicitly and unsupported provider reasons fail closed", () => {
  assert.equal(mapFinishReason("stop", false), "end_turn");
  assert.equal(mapFinishReason("stop", true), "tool_use");
  assert.equal(mapFinishReason("length", false), "max_tokens");
  assert.equal(mapFinishReason("tool_calls", true), "tool_use");
  assert.throws(() => mapFinishReason("tool_calls", false), /did not include tool_calls/);
  assert.throws(() => mapFinishReason("content_filter", false), /does not map it to an Anthropic safety verdict/);
  assert.throws(() => mapFinishReason("provider_magic", false), /Unsupported or missing upstream finish_reason/);
  assert.throws(() => mapFinishReason(null, false), /Unsupported or missing upstream finish_reason/);
  assert.throws(() => mapFinishReason("function_call", false), /without stable tool-call IDs/);
});
