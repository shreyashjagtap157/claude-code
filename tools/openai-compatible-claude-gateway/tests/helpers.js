import http from "node:http";
import { loadConfig } from "../src/config.js";
import { createGatewayServer } from "../src/server.js";

export async function listen(server) {
  await new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", () => { server.off("error", reject); resolve(); }); });
  return `http://127.0.0.1:${server.address().port}`;
}

export async function close(server) {
  if (!server?.listening) return;
  await new Promise(resolve => server.close(() => resolve()));
}

export function createFakeUpstream({ requests = [], mode = "normal", onStreamClose } = {}) {
  const server = http.createServer(async (req, res) => {
    if (req.method === "GET" && req.url?.endsWith("/models")) { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify({ data: [{ id: "fake-model" }] })); return; }
    let raw = ""; for await (const chunk of req) raw += chunk.toString("utf8");
    let body; try { body = JSON.parse(raw); } catch { body = {}; }
    requests.push({ headers: { authorization: req.headers.authorization, local: req.headers["x-local-auth"] }, body });
    if (mode === "safeguard-results") { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify({ id: "chatcmpl_safety", safeguard_results: { allow: true }, choices: [{ index: 0, message: { role: "assistant", content: "Must not be accepted as Anthropic safety validation." }, finish_reason: "stop" }] })); return; }
    if (mode === "http-error") { res.writeHead(401, { "content-type": "application/json" }); res.end('{"error":"private detail must not escape"}'); return; }
    if (mode === "invalid-json") { res.writeHead(200, { "content-type": "application/json" }); res.end("not json"); return; }
    if (body.stream && mode === "json-stream-response") { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify({ choices: [{ message: { content: "not actually streamed" }, finish_reason: "stop" }] })); return; }
    if (body.stream) {
      res.once("close", () => onStreamClose?.());
      res.writeHead(200, { "content-type": "text/event-stream" }); const prompt = JSON.stringify(body); const emit = value => res.write(value); const event = payload => `data: ${JSON.stringify(payload)}\n\n`;
      if (mode === "invalid-sse") { emit("data: {not-json}\n\n"); emit("data: [DONE]\n\n"); res.end(); return; }
      if (mode === "missing-done") { emit(event({ choices: [{ index: 0, delta: { content: "partial" }, finish_reason: null }] })); emit(event({ choices: [{ index: 0, delta: {}, finish_reason: "stop" }] })); res.end(); return; }
      if (mode === "stream-reset") {
        res.flushHeaders();
        emit(event({ choices: [{ index: 0, delta: { content: "partial" }, finish_reason: null }] }));
        setTimeout(() => { if (!res.destroyed) res.destroy(); }, 25);
        return;
      }
      if (mode === "stream-idle") {
        res.flushHeaders();
        setTimeout(() => { if (!res.destroyed) res.destroy(); }, 1000).unref?.();
        return;
      }
      if (prompt.includes("stream-malformed-tool")) {
        const chunks = [
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: "call_bad_args", type: "function", function: { name: "weather", arguments: "{\"city\":" } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: "not-json" } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }] }
        ];
        for (const chunk of chunks) emit(event(chunk));
      } else if (prompt.includes("stream-multi-tool")) {
        const chunks = [
          { choices: [{ index: 0, delta: { tool_calls: [
            { index: 0, id: "call_weather", type: "function", function: { name: "weather", arguments: "" } },
            { index: 1, id: "call_lookup", type: "function", function: { name: "lookup", arguments: "" } }
          ] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [
            { index: 1, function: { arguments: '{"term":' } },
            { index: 0, function: { arguments: '{"city":"Pune"}' } }
          ] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 1, function: { arguments: '"forecast"}' } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }] },
          { choices: [], usage: { prompt_tokens: 12, completion_tokens: 8, total_tokens: 20 } }
        ];
        for (const chunk of chunks) emit(event(chunk));
      } else if (prompt.includes("stream-tool")) {
        const chunks = [
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, id: "call_stream_1", type: "function", function: { name: "wea" } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { name: "ther", arguments: "" } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: '{"city":' } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: '"Pune"}' } }] }, finish_reason: null }] },
          { choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }] },
          { choices: [], usage: { prompt_tokens: 12, completion_tokens: 4, total_tokens: 16 } }
        ]; for (const chunk of chunks) emit(event(chunk));
      } else {
        const pieces = [
          `data: ${JSON.stringify({ choices: [{ index: 0, delta: { content: "Hel" }, finish_reason: null }] })}\r\n\r\n`,
          `: keepalive\r\n\r\n`,
          `data: ${JSON.stringify({ choices: [{ index: 0, delta: { content: "lo" }, finish_reason: null }] })}\n\n`,
          `data: ${JSON.stringify({ choices: [{ index: 0, delta: {}, finish_reason: "stop" }] })}\n\n`,
          `data: ${JSON.stringify({ choices: [], usage: { prompt_tokens: 7, completion_tokens: 2, total_tokens: 9 } })}\n\n`
        ]; for (const piece of pieces) for (let i = 0; i < piece.length; i += 7) emit(piece.slice(i, i + 7));
      }
      if (mode !== "missing-done") emit("data: [DONE]\r\n\r\n"); res.end(); return;
    }
    const messages = body.messages || []; let payload;
    if (messages.some(item => item.role === "tool")) payload = { id: "chatcmpl_final", choices: [{ index: 0, message: { role: "assistant", content: "Tool result received." }, finish_reason: "stop" }], usage: { prompt_tokens: 19, completion_tokens: 5, total_tokens: 24 } };
    else if (messages.at(-1)?.content === "use a tool") payload = { id: "chatcmpl_tool", choices: [{ index: 0, message: { role: "assistant", content: null, tool_calls: [{ id: "call_exact_123", type: "function", function: { name: "weather", arguments: "{\"city\":\"Pune\"}" } }] }, finish_reason: "tool_calls" }], usage: { prompt_tokens: 9, completion_tokens: 3, total_tokens: 12 } };
    else payload = { id: "chatcmpl_text", choices: [{ index: 0, message: { role: "assistant", content: "Hello from the fake upstream." }, finish_reason: "stop" }], usage: { prompt_tokens: 10, completion_tokens: 6, total_tokens: 16 } };
    res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify(payload));
  });
  return server;
}

export function makeConfig(upstreamBaseUrl, overrides = {}) {
  return loadConfig({ cwd: "/definitely-not-a-real-gateway-dir", env: {
    OPENAI_COMPATIBLE_BASE_URL: upstreamBaseUrl, OPENAI_COMPATIBLE_MODEL: "fake-model", OPENAI_COMPATIBLE_API_KEY: "upstream-secret-fixture",
    GATEWAY_HOST: "127.0.0.1", GATEWAY_PORT: "3456", ...overrides
  } });
}

export async function startGateway(upstreamBaseUrl, overrides = {}) {
  const config = makeConfig(upstreamBaseUrl, overrides); const gateway = createGatewayServer(config); const url = await listen(gateway);
  return { gateway, url, config };
}
