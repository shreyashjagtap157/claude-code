import test from "node:test";
import assert from "node:assert/strict";
import { createClaudeChildEnvironment } from "../src/launcher-env.js";

test("launcher child environment isolates upstream credentials, selects local token and opts out of server classifier", () => {
  const parent = { ANTHROPIC_API_KEY: "preexisting-provider-key", ANTHROPIC_AUTH_TOKEN: "preexisting-token", OPENAI_COMPATIBLE_API_KEY: "upstream-key-fixture", OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1", OPENAI_COMPATIBLE_MODEL_CAPABILITIES: "private-model-capability-config", GATEWAY_API_KEY: "local-key-fixture", GATEWAY_ENV_FILE: "private-env-path", GATEWAY_CONFIG_FILE: "private-config-path", GATEWAY_BASE_URL: "http://remote.example:3456", GATEWAY_HOST: "0.0.0.0", GATEWAY_PORT: "9999", GATEWAY_MAX_OUTPUT_TOKENS: "77", OTHER_SETTING: "unchanged" };
  const before = { ...parent }; const child = createClaudeChildEnvironment(parent, { gatewayBaseUrl: "http://127.0.0.1:3456", gatewayApiKey: "local-key-fixture" });
  assert.equal(child.ANTHROPIC_BASE_URL, "http://127.0.0.1:3456"); assert.equal(child.CLAUDE_CODE_AUTO_MODE_SERVER, "0"); assert.equal(child.ANTHROPIC_AUTH_TOKEN, "local-key-fixture");
  assert.equal(child.CLAUDE_CODE_ATTRIBUTION_HEADER, "0");
  assert.equal(child.CLAUDE_CODE_DISABLE_THINKING, "1");
  assert.equal(child.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS, "1");
  assert.equal(child.CLAUDE_CODE_EFFORT_LEVEL, "auto");
  assert.equal(child.ANTHROPIC_API_KEY, undefined); assert.equal(child.OPENAI_COMPATIBLE_API_KEY, undefined); assert.equal(child.OPENAI_COMPATIBLE_BASE_URL, undefined); assert.equal(child.OPENAI_COMPATIBLE_MAX_TOKENS_FIELD, undefined); assert.equal(child.OPENAI_COMPATIBLE_MODEL_PASSTHROUGH, undefined); assert.equal(child.OPENAI_COMPATIBLE_MODEL_CAPABILITIES, undefined); assert.equal(child.GATEWAY_API_KEY, undefined); assert.equal(child.GATEWAY_ENV_FILE, undefined); assert.equal(child.GATEWAY_CONFIG_FILE, undefined); assert.equal(child.GATEWAY_BASE_URL, undefined); assert.equal(child.GATEWAY_HOST, undefined); assert.equal(child.GATEWAY_PORT, undefined); assert.equal(child.GATEWAY_MAX_OUTPUT_TOKENS, undefined); assert.equal(child.OTHER_SETTING, "unchanged"); assert.deepEqual(parent, before);
});

test("launcher does not invent a local credential when none is configured", () => {
  const child = createClaudeChildEnvironment({ ANTHROPIC_AUTH_TOKEN: "stale" }, { gatewayBaseUrl: "http://127.0.0.1:3456" });
  assert.equal(child.ANTHROPIC_AUTH_TOKEN, undefined); assert.equal(child.ANTHROPIC_API_KEY, undefined); assert.equal(child.CLAUDE_CODE_AUTO_MODE_SERVER, "0");
  assert.equal(child.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS, "1");
});


test("launcher defaults empty beta and effort values consistently with shell wrappers", () => {
  const child = createClaudeChildEnvironment({ CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS: "", CLAUDE_CODE_EFFORT_LEVEL: "" }, { gatewayBaseUrl: "http://127.0.0.1:3456" });
  assert.equal(child.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS, "1");
  assert.equal(child.CLAUDE_CODE_EFFORT_LEVEL, "auto");
});

test("launcher preserves explicit beta and effort overrides", () => {
  const child = createClaudeChildEnvironment({ CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS: "0", CLAUDE_CODE_EFFORT_LEVEL: "low" }, { gatewayBaseUrl: "http://127.0.0.1:3456" });
  assert.equal(child.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS, "0");
  assert.equal(child.CLAUDE_CODE_EFFORT_LEVEL, "low");
});
