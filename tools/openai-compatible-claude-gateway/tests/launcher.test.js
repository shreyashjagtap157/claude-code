import test from "node:test";
import assert from "node:assert/strict";
import { createClaudeChildEnvironment } from "../src/launcher-env.js";

test("launcher child environment isolates upstream credentials, selects local token and opts out of server classifier", () => {
  const parent = { ANTHROPIC_API_KEY: "preexisting-provider-key", ANTHROPIC_AUTH_TOKEN: "preexisting-token", OPENAI_COMPATIBLE_API_KEY: "upstream-key-fixture", OPENAI_COMPATIBLE_BASE_URL: "https://provider.example/v1", GATEWAY_API_KEY: "local-key-fixture", OTHER_SETTING: "unchanged" };
  const before = { ...parent }; const child = createClaudeChildEnvironment(parent, { gatewayBaseUrl: "http://127.0.0.1:3456", gatewayApiKey: "local-key-fixture" });
  assert.equal(child.ANTHROPIC_BASE_URL, "http://127.0.0.1:3456"); assert.equal(child.CLAUDE_CODE_AUTO_MODE_SERVER, "0"); assert.equal(child.ANTHROPIC_AUTH_TOKEN, "local-key-fixture");
  assert.equal(child.ANTHROPIC_API_KEY, undefined); assert.equal(child.OPENAI_COMPATIBLE_API_KEY, undefined); assert.equal(child.OPENAI_COMPATIBLE_BASE_URL, undefined); assert.equal(child.GATEWAY_API_KEY, undefined); assert.equal(child.OTHER_SETTING, "unchanged"); assert.deepEqual(parent, before);
});

test("launcher does not invent a local credential when none is configured", () => {
  const child = createClaudeChildEnvironment({ ANTHROPIC_AUTH_TOKEN: "stale" }, { gatewayBaseUrl: "http://127.0.0.1:3456" });
  assert.equal(child.ANTHROPIC_AUTH_TOKEN, undefined); assert.equal(child.ANTHROPIC_API_KEY, undefined); assert.equal(child.CLAUDE_CODE_AUTO_MODE_SERVER, "0");
});
