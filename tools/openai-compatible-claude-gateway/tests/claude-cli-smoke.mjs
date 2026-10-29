import http from "node:http";
import { spawn } from "node:child_process";
import { createClaudeChildEnvironment } from "../src/launcher-env.js";
import { loadConfig } from "../src/config.js";
import { createGatewayServer } from "../src/server.js";

const EXPECTED = "GATEWAY_CLI_SMOKE_OK";
const LOCAL_TOKEN = "gateway-cli-smoke-local-token";
const upstreamRequests = [];
const gatewayErrors = [];
const originalStdoutWrite = process.stdout.write;
process.stdout.write = function (chunk, ...args) {
  if (typeof chunk === "string") {
    for (const line of chunk.split("\\n")) {
      try {
        const event = JSON.parse(line);
        if (event?.event === "request_failed") gatewayErrors.push({ code: event.code, status: event.status, detail: event.detail });
      } catch { /* non-JSON application output is not a gateway log event */ }
    }
  }
  return originalStdoutWrite.call(this, chunk, ...args);
};
let gateway;
let upstream;

function listen(server) {
  return new Promise((resolve, reject) => {
    const onError = error => { server.off("listening", onListening); reject(error); };
    const onListening = () => { server.off("error", onError); resolve(server.address()); };
    server.once("error", onError);
    server.once("listening", onListening);
    server.listen(0, "127.0.0.1");
  });
}

function closeServer(server) {
  if (!server?.listening) return Promise.resolve();
  return new Promise(resolve => server.close(() => resolve()));
}

function run(binary, args, env, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(binary, args, { env, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill("SIGTERM");
      setTimeout(() => { if (child.exitCode === null) child.kill("SIGKILL"); }, 1500).unref?.();
      reject(new Error(`Claude Code CLI timed out after ${timeoutMs} ms.`));
    }, timeoutMs);
    timeout.unref?.();
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", chunk => { stdout += chunk; });
    child.stderr.on("data", chunk => { stderr += chunk; });
    child.once("error", error => { clearTimeout(timeout); reject(error); });
    child.once("close", (code, signal) => {
      clearTimeout(timeout);
      resolve({ code: code ?? 1, signal, stdout, stderr });
    });
  });
}

async function main() {
  upstream = http.createServer(async (request, response) => {
    if (request.method !== "POST" || new URL(request.url || "/", "http://127.0.0.1").pathname !== "/v1/chat/completions") {
      response.writeHead(404, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: { message: "The CLI smoke fake upstream only supports /v1/chat/completions." } }));
      return;
    }
    let text = "";
    for await (const chunk of request) text += chunk.toString("utf8");
    let body;
    try { body = JSON.parse(text); } catch {
      response.writeHead(400, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: { message: "Invalid JSON sent by gateway." } }));
      return;
    }
    upstreamRequests.push({
      model: body.model,
      stream: body.stream === true,
      authorizationPresent: typeof request.headers.authorization === "string",
      hasLocalTokenInBody: text.includes(LOCAL_TOKEN),
      messageCount: Array.isArray(body.messages) ? body.messages.length : 0
    });
    if (body.stream === true) {
      response.writeHead(200, { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-cache" });
      const event = payload => response.write(`data: ${JSON.stringify(payload)}\n\n`);
      event({ id: "chatcmpl_cli_smoke", object: "chat.completion.chunk", model: "deterministic-smoke-model", choices: [{ index: 0, delta: { role: "assistant", content: EXPECTED }, finish_reason: null }] });
      event({ id: "chatcmpl_cli_smoke", object: "chat.completion.chunk", model: "deterministic-smoke-model", choices: [{ index: 0, delta: {}, finish_reason: "stop" }] });
      event({ id: "chatcmpl_cli_smoke", object: "chat.completion.chunk", model: "deterministic-smoke-model", choices: [], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } });
      response.write("data: [DONE]\n\n");
      response.end();
    } else {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: "chatcmpl_cli_smoke", object: "chat.completion", model: "deterministic-smoke-model", choices: [{ index: 0, message: { role: "assistant", content: EXPECTED }, finish_reason: "stop" }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
    }
  });
  const upstreamAddress = await listen(upstream);
  const config = loadConfig({ cwd: process.cwd(), env: {
    OPENAI_COMPATIBLE_BASE_URL: `http://127.0.0.1:${upstreamAddress.port}/v1`,
    OPENAI_COMPATIBLE_MODEL: "deterministic-smoke-model",
    OPENAI_COMPATIBLE_CAPABILITIES: JSON.stringify({ streaming: true, toolCalling: true, parallelToolCalls: false, images: false, jsonSchema: false, reasoningEffort: false, temperature: true, topP: true, stopSequences: true, streamUsage: true, streamRequiresDone: true }),
    GATEWAY_HOST: "127.0.0.1", GATEWAY_PORT: "3456", GATEWAY_API_KEY: LOCAL_TOKEN,
    GATEWAY_REQUEST_TIMEOUT_MS: "45000", GATEWAY_STREAM_IDLE_TIMEOUT_MS: "15000",
    GATEWAY_MAX_BODY_BYTES: "10485760", GATEWAY_MAX_CONCURRENT_REQUESTS: "4", GATEWAY_LOG_LEVEL: "error"
  } });
  gateway = createGatewayServer(config);
  const gatewayAddress = await listen(gateway);
  const gatewayBaseUrl = `http://127.0.0.1:${gatewayAddress.port}`;
  const env = createClaudeChildEnvironment(process.env, { gatewayBaseUrl, gatewayApiKey: LOCAL_TOKEN });
  env.ANTHROPIC_MODEL = "sonnet";
  env.CLAUDE_CODE_AUTO_MODE_SERVER = "0";
  env.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1";
  env.CLAUDE_CODE_DISABLE_THINKING = "1";
  env.CLAUDE_CODE_ATTRIBUTION_HEADER = "0";
  env.DISABLE_AUTOUPDATER = "1";
  env.DISABLE_TELEMETRY = "1";
  env.DISABLE_ERROR_REPORTING = "1";
  env.DO_NOT_TRACK = "1";
  delete env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC;
  delete env.OPENAI_COMPATIBLE_API_KEY;
  delete env.GATEWAY_API_KEY;
  const binary = process.env.CLAUDE_BIN || "claude";
  try {
    const version = await run(binary, ["--version"], env, 20000);
    if (version.code !== 0 || !version.stdout.trim()) throw new Error(`Claude Code --version failed (exit ${version.code}). stderr: ${version.stderr.slice(-2000)}`);
    process.stdout.write(`Claude Code CLI version: ${version.stdout.trim()}\n`);
    const result = await run(binary, ["-p", "Reply with the exact string GATEWAY_CLI_SMOKE_OK and nothing else.", "--output-format", "text", "--model", "sonnet", "--max-turns", "1"], env, 90000);
    if (result.code !== 0) throw new Error(`Claude Code CLI exited ${result.code} (signal ${result.signal || "none"}). stdout tail: ${result.stdout.slice(-3000)} stderr tail: ${result.stderr.slice(-3000)}`);
    if (!result.stdout.includes(EXPECTED)) throw new Error(`CLI output did not include the deterministic response. stdout tail: ${result.stdout.slice(-3000)} stderr tail: ${result.stderr.slice(-3000)}`);
    if (!upstreamRequests.length) throw new Error("Claude Code CLI completed without reaching the configured fake upstream.");
    if (gatewayErrors.length) throw new Error(`Gateway rejected ${gatewayErrors.length} request(s) during real CLI smoke: ${JSON.stringify(gatewayErrors)}`);
    if (upstreamRequests.some(item => item.authorizationPresent || item.hasLocalTokenInBody)) throw new Error("Local gateway credentials leaked to the fake upstream.");
    process.stdout.write(JSON.stringify({
      result: "passed",
      cliVersion: version.stdout.trim(),
      upstreamRequests: upstreamRequests.length,
      streamedRequests: upstreamRequests.filter(item => item.stream).length,
      model: upstreamRequests[0].model,
      upstreamAuthorizationPresent: false,
      billableProviderCalls: 0
    }, null, 2) + "\n");
  } finally {
    gateway?.closeActiveGatewayRequests?.();
    await closeServer(gateway);
    await closeServer(upstream);
    process.stdout.write = originalStdoutWrite;
  }
}

main().catch(error => {
  process.stderr.write(`Claude CLI smoke failed: ${error?.message || "unknown error"}\n`);
  process.exitCode = 1;
});
