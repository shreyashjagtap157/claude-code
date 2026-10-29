import test from "node:test";
import assert from "node:assert/strict";
import { loadConfig, resolveModel, resolveCapabilities, configInternals } from "../src/config.js";
import { ConfigError } from "../src/errors.js";

function envFor(baseUrl, more = {}) { return { OPENAI_COMPATIBLE_BASE_URL: baseUrl, OPENAI_COMPATIBLE_MODEL: "default-model", ...more }; }

test("required config and conservative capability defaults", () => {
  assert.throws(() => loadConfig({ env: {}, cwd: "/no-env" }), /OPENAI_COMPATIBLE_BASE_URL is required/);
  const cfg = loadConfig({ env: envFor("https://provider.example/v1"), cwd: "/no-env" });
  assert.equal(cfg.port, 3456); assert.equal(cfg.host, "127.0.0.1"); assert.equal(cfg.upstreamUrl.pathname, "/v1/chat/completions");
  assert.equal(cfg.capabilities.toolCalling, false); assert.equal(cfg.capabilities.images, false); assert.equal(cfg.logLevel, "info");
  assert.throws(() => loadConfig({ env: envFor("https://provider.example/v1", { GATEWAY_LOG_LEVEL: "verbose-please" }), cwd: "/no-env" }), /GATEWAY_LOG_LEVEL must be/);
});

test("normalizes root, v1, custom-prefix and full chat-completions URLs exactly once", () => {
  const cases = [["https://provider.example", "/v1/chat/completions"], ["https://provider.example/v1", "/v1/chat/completions"], ["https://provider.example/custom/openai/v1", "/custom/openai/v1/chat/completions"], ["https://provider.example/v1/chat/completions", "/v1/chat/completions"], ["https://provider.example/custom/v1/chat/completions/", "/custom/v1/chat/completions"], ["https://provider.example/prefix", "/prefix/v1/chat/completions"]];
  for (const [url, expected] of cases) { const cfg = loadConfig({ env: envFor(url), cwd: "/no-env" }); assert.equal(cfg.upstreamUrl.pathname, expected, url); assert.equal((cfg.upstreamUrl.pathname.match(/chat\/completions/g) || []).length, 1); assert.equal(cfg.upstreamUrl.pathname.includes("/v1/v1"), false); }
});

test("explicit endpoint path replaces URL path and preserves configured query parameters", () => {
  const cfg = loadConfig({ env: envFor("https://provider.example/prefix?tenant=demo", { OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH: "/openai/v1/chat/completions" }), cwd: "/no-env" });
  assert.equal(cfg.upstreamUrl.pathname, "/openai/v1/chat/completions"); assert.equal(cfg.upstreamUrl.searchParams.get("tenant"), "demo"); assert.equal(cfg.modelsUrl.pathname, "/openai/v1/models"); assert.equal(cfg.displayEndpoint, "https://provider.example/openai/v1/chat/completions");
});

test("rejects malformed URLs, embedded credentials, invalid protocols, fragments and malformed path overrides", () => {
  for (const url of ["not a URL", "ftp://provider.example/v1", "https://user:pass@provider.example/v1", "https://provider.example/v1#fragment", "https://provider.example:99999/v1"]) assert.throws(() => loadConfig({ env: envFor(url), cwd: "/no-env" }), ConfigError, url);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example/v1", { OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH: "relative/chat/completions" }), cwd: "/no-env" }), /must be an absolute/);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example/v1", { OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH: "/v1/completions" }), cwd: "/no-env" }), /must end with/);
});

test("HTTP upstreams are allowed on loopback but blocked elsewhere unless explicitly opted in", () => {
  assert.equal(loadConfig({ env: envFor("http://127.0.0.1:11434/v1"), cwd: "/no-env" }).upstreamUrl.origin, "http://127.0.0.1:11434");
  assert.equal(configInternals.isLoopback("localhost"), true); assert.equal(configInternals.isLoopback("::1"), true);
  assert.throws(() => loadConfig({ env: envFor("http://provider.example/v1"), cwd: "/no-env" }), /must use HTTPS/);
  assert.equal(loadConfig({ env: envFor("http://provider.example/v1", { OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP: "true" }), cwd: "/no-env" }).upstreamUrl.protocol, "http:");
});

test("remote gateway binding requires deliberate opt-in and a local credential", () => {
  assert.throws(() => loadConfig({ env: envFor("https://provider.example/v1", { GATEWAY_HOST: "0.0.0.0" }), cwd: "/no-env" }), /requires both/);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example/v1", { GATEWAY_HOST: "0.0.0.0", GATEWAY_ALLOW_REMOTE: "true" }), cwd: "/no-env" }), /requires both/);
  const cfg = loadConfig({ env: envFor("https://provider.example/v1", { GATEWAY_HOST: "0.0.0.0", GATEWAY_ALLOW_REMOTE: "true", GATEWAY_API_KEY: "local" }), cwd: "/no-env" }); assert.equal(cfg.host, "0.0.0.0");
});

test("validates model map, capabilities, integer limits and model fallback policy", () => {
  const cfg = loadConfig({ env: { OPENAI_COMPATIBLE_BASE_URL: "https://provider.example", OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-sonnet":"remote-model"}' }, cwd: "/no-env" });
  assert.equal(resolveModel("claude-sonnet", cfg), "remote-model");
  const hostileMap = loadConfig({ env: { OPENAI_COMPATIBLE_BASE_URL: "https://provider.example", OPENAI_COMPATIBLE_MODEL_MAP: '{"__proto__":"attacker-model","normal":"safe-model"}' }, cwd: "/no-env" });
  assert.equal(resolveModel("__proto__", hostileMap), "attacker-model"); assert.equal(Object.getPrototypeOf(hostileMap.modelMap), null);
  assert.throws(() => resolveModel("unknown", cfg), /No upstream model is configured/);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example", { OPENAI_COMPATIBLE_MODEL_MAP: "[]" }), cwd: "/no-env" }), /must be a JSON object/);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example", { OPENAI_COMPATIBLE_CAPABILITIES: '{"mystery":true}' }), cwd: "/no-env" }), /Unknown capability key/);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example", { OPENAI_COMPATIBLE_CAPABILITIES: '{"parallelToolCalls":true}' }), cwd: "/no-env" }), /requires toolCalling/);
  assert.throws(() => loadConfig({ env: envFor("https://provider.example", { GATEWAY_PORT: "70000" }), cwd: "/no-env" }), /between 1 and 65535/);
  const pass = loadConfig({ env: { OPENAI_COMPATIBLE_BASE_URL: "https://provider.example", OPENAI_COMPATIBLE_MODEL_PASSTHROUGH: "true" }, cwd: "/no-env" }); assert.equal(resolveModel("provider-custom-id", pass), "provider-custom-id");
});

test("process environment wins over .env values without mutating supplied environment", () => {
  const incoming = envFor("https://shell.example/v1", { OPENAI_COMPATIBLE_MODEL: "shell-model" }); const copy = { ...incoming };
  const cfg = loadConfig({ env: incoming, cwd: "/no-env" }); assert.equal(cfg.defaultModel, "shell-model"); assert.deepEqual(incoming, copy);
});


test("dedicated max-token field override validates and takes precedence over capability JSON", () => {
  const cfg = loadConfig({ env: envFor("https://provider.example/v1", {
    OPENAI_COMPATIBLE_CAPABILITIES: '{"maxTokensField":"max_tokens"}',
    OPENAI_COMPATIBLE_MAX_TOKENS_FIELD: "max_completion_tokens"
  }), cwd: "/no-env" });
  assert.equal(cfg.capabilities.maxTokensField, "max_completion_tokens");
  assert.throws(() => loadConfig({ env: envFor("https://provider.example/v1", {
    OPENAI_COMPATIBLE_MAX_TOKENS_FIELD: "max_new_tokens"
  }), cwd: "/no-env" }), /OPENAI_COMPATIBLE_MAX_TOKENS_FIELD must be max_tokens or max_completion_tokens/);
});


test("per-model capability overrides resolve upstream-first and requested-alias-last", () => {
  const cfg = loadConfig({ cwd: "/no-env", env: {
    OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1",
    OPENAI_COMPATIBLE_MODEL: "fallback-model",
    OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-vision":"vision-model","claude-tools":"tool-model"}',
    OPENAI_COMPATIBLE_CAPABILITIES: '{"toolCalling":false,"images":false}',
    OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '{"vision-model":{"images":true,"toolCalling":true},"claude-vision":{"images":false},"tool-model":{"toolCalling":true}}'
  }});
  const vision = resolveCapabilities("claude-vision", "vision-model", cfg);
  assert.equal(vision.toolCalling, true);
  assert.equal(vision.images, false, "exact requested alias takes precedence over upstream model ID");
  const tools = resolveCapabilities("claude-tools", "tool-model", cfg);
  assert.equal(tools.toolCalling, true);
  assert.equal(tools.images, false);
  const defaultRoute = resolveCapabilities("unknown-claude-alias", "fallback-model", cfg);
  assert.equal(defaultRoute.images, false);
});

test("per-model capability override JSON rejects unknown names, invalid types, and invalid tool combinations", () => {
  const base = { OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1", OPENAI_COMPATIBLE_MODEL: "fallback" };
  assert.throws(() => loadConfig({ cwd: "/no-env", env: { ...base, OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '{"m":{"mystery":true}}' } }), /Unknown capability key mystery/);
  assert.throws(() => loadConfig({ cwd: "/no-env", env: { ...base, OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '{"m":{"images":"yes"}}' } }), /images must be boolean/);
  assert.throws(() => loadConfig({ cwd: "/no-env", env: { ...base, OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '{"m":{"parallelToolCalls":true}}' } }), /parallelToolCalls=true requires toolCalling=true/);
  assert.throws(() => loadConfig({ cwd: "/no-env", env: { ...base, OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '[]' } }), /must be a JSON object mapping model IDs/);
});


test("per-model capability IDs reject newline characters instead of mis-parsing them", () => {
  const base = { OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1", OPENAI_COMPATIBLE_MODEL: "fallback" };
  const withNewline = JSON.stringify({ ["bad\nmodel"]: { images: true } });
  assert.throws(() => loadConfig({ cwd: "/no-env", env: { ...base, OPENAI_COMPATIBLE_MODEL_CAPABILITIES: withNewline } }), /keys must be non-empty model IDs/);
});


test("partial overrides can combine capabilities across the upstream ID and client alias", () => {
  const cfg = loadConfig({ cwd: "/no-env", env: {
    OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1",
    OPENAI_COMPATIBLE_MODEL: "fallback",
    OPENAI_COMPATIBLE_MODEL_MAP: '{"claude-tools":"tool-model"}',
    OPENAI_COMPATIBLE_CAPABILITIES: '{"toolCalling":false,"parallelToolCalls":false}',
    OPENAI_COMPATIBLE_MODEL_CAPABILITIES: '{"tool-model":{"toolCalling":true},"claude-tools":{"parallelToolCalls":true}}'
  }});
  const caps = resolveCapabilities("claude-tools", "tool-model", cfg);
  assert.equal(caps.toolCalling, true);
  assert.equal(caps.parallelToolCalls, true);
});


test("gateway output-token upper bound is configurable and defaults to one million", () => {
  const base = { OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1", OPENAI_COMPATIBLE_MODEL: "model" };
  assert.equal(loadConfig({ cwd: "/no-env", env: base }).maxOutputTokens, 1_000_000);
  assert.equal(loadConfig({ cwd: "/no-env", env: { ...base, GATEWAY_MAX_OUTPUT_TOKENS: "4096" } }).maxOutputTokens, 4096);
  assert.throws(() => loadConfig({ cwd: "/no-env", env: { ...base, GATEWAY_MAX_OUTPUT_TOKENS: "0" } }), /GATEWAY_MAX_OUTPUT_TOKENS must be between 1 and 2147483647/);
});
