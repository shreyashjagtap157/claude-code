import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const launcher = path.join(packageRoot, "scripts", "start-claude-with-openai-provider.sh");
function listen(server) { return new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", () => { server.off("error", reject); resolve(server.address().port); }); }); }
function close(server) { return new Promise(resolve => server.close(() => resolve())); }
function runChild(command, args, options, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, options); let stdout = ""; let stderr = "";
    const timer = setTimeout(() => { child.kill(); reject(new Error(`Child process timed out after ${timeoutMs} ms.`)); }, timeoutMs);
    child.stdout.setEncoding("utf8"); child.stderr.setEncoding("utf8"); child.stdout.on("data", chunk => { stdout += chunk; }); child.stderr.on("data", chunk => { stderr += chunk; });
    child.once("error", error => { clearTimeout(timer); reject(error); }); child.once("close", (code, signal) => { clearTimeout(timer); resolve({ status: code ?? (signal ? 128 : 1), stdout, stderr, signal }); });
  });
}

test("server reports an occupied port and leaves the existing listener running", async t => {
  const listener = http.createServer((_request, response) => { response.writeHead(200); response.end("still-running"); }); const port = await listen(listener); t.after(() => close(listener));
  const env = { ...process.env, OPENAI_COMPATIBLE_BASE_URL: "http://127.0.0.1:8000/v1", OPENAI_COMPATIBLE_MODEL: "fake-model", GATEWAY_HOST: "127.0.0.1", GATEWAY_PORT: String(port) };
  for (const key of ["GATEWAY_CONFIG_FILE", "GATEWAY_ENV_FILE", "GATEWAY_API_KEY", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_MODEL_MAP", "OPENAI_COMPATIBLE_CAPABILITIES"]) delete env[key];
  const child = spawnSync(process.execPath, [path.join(packageRoot, "src", "main.js")], { cwd: packageRoot, env, encoding: "utf8", timeout: 5000 });
  assert.equal(child.status, 1, `expected exit 1, got ${child.status}; stderr=${child.stderr}`); assert.match(child.stderr, /port is already in use/); assert.match(child.stderr, /No process was stopped/);
  const stillListening = await fetch(`http://127.0.0.1:${port}/`); assert.equal(stillListening.status, 200); assert.equal(await stillListening.text(), "still-running");
});

test("POSIX launcher builds isolated child environment and selects the local classifier path", async t => {
  const healthServer = http.createServer((_request, response) => { response.writeHead(200, { "content-type": "application/json" }); response.end('{"status":"ok"}'); }); const port = await listen(healthServer); t.after(() => close(healthServer));
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "claude-gateway-launcher-test-")); t.after(() => fs.rmSync(tempDir, { recursive: true, force: true }));
  const fakeCli = path.join(tempDir, "fake-claude.sh"); fs.writeFileSync(fakeCli, '#!/bin/sh\nprintf "base=%s\\nlocal=%s\\nserver=%s\\nupstream=%s\\nanthropic_api=%s\\ngateway=%s\\n" "${ANTHROPIC_BASE_URL-unset}" "${ANTHROPIC_AUTH_TOKEN-unset}" "${CLAUDE_CODE_AUTO_MODE_SERVER-unset}" "${OPENAI_COMPATIBLE_API_KEY-unset}" "${ANTHROPIC_API_KEY-unset}" "${GATEWAY_API_KEY-unset}"\n', { mode: 0o755 });
  const env = { ...process.env, CLAUDE_BIN: fakeCli, GATEWAY_BASE_URL: `http://127.0.0.1:${port}`, GATEWAY_API_KEY: "local-launch-fixture", OPENAI_COMPATIBLE_API_KEY: "upstream-launch-secret-fixture", ANTHROPIC_API_KEY: "old-anthropic-key-fixture", ANTHROPIC_AUTH_TOKEN: "old-anthropic-token-fixture" };
  const child = await runChild("sh", [launcher, "--fixture-arg"], { cwd: tempDir, env, stdio: ["ignore", "pipe", "pipe"] }); assert.equal(child.status, 0, child.stderr);
  assert.match(child.stdout, /base=http:\/\/127\.0\.0\.1:\d+/); assert.match(child.stdout, /local=local-launch-fixture/); assert.match(child.stdout, /server=0/); assert.match(child.stdout, /upstream=unset/); assert.match(child.stdout, /anthropic_api=unset/); assert.match(child.stdout, /gateway=unset/);
  assert.equal(child.stdout.includes("upstream-launch-secret-fixture"), false); assert.equal(env.ANTHROPIC_AUTH_TOKEN, "old-anthropic-token-fixture", "parent environment object remains unchanged");
});
