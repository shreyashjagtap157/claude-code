import http from "node:http";
import { randomUUID, timingSafeEqual, createHash } from "node:crypto";
import { GatewayError, UpstreamError, UpstreamProtocolError, anthropicError, publicUpstreamError } from "./errors.js";
import { translateAnthropicRequest } from "./translate/request.js";
import { translateChatCompletionResponse } from "./translate/response.js";
import { streamChatCompletion, writeSse } from "./translate/stream.js";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

const LOG_LEVELS = Object.freeze({ debug: 10, info: 20, warn: 30, error: 40, silent: Infinity });
function logEvent(level, event, fields = {}, minimumLevel = "info") {
  if ((LOG_LEVELS[level] ?? LOG_LEVELS.info) < (LOG_LEVELS[minimumLevel] ?? LOG_LEVELS.info)) return;
  const allowed = { event, ...fields };
  // Log only explicitly selected metadata. Never log URLs, request bodies, headers or raw exceptions.
  process.stdout.write(`${JSON.stringify({ timestamp: new Date().toISOString(), level, ...allowed })}\n`);
}

function sameSecret(a, b) {
  const left = createHash("sha256").update(String(a)).digest();
  const right = createHash("sha256").update(String(b)).digest();
  return timingSafeEqual(left, right);
}

function suppliedLocalCredential(request) {
  const authorization = request.headers.authorization;
  if (typeof authorization === "string" && /^Bearer\s+/i.test(authorization)) return authorization.replace(/^Bearer\s+/i, "");
  const xApiKey = request.headers["x-api-key"];
  return typeof xApiKey === "string" ? xApiKey : "";
}

function requireLocalAuth(request, config) {
  if (!config.gatewayApiKey) return;
  const received = suppliedLocalCredential(request);
  if (!received || !sameSecret(received, config.gatewayApiKey)) throw new GatewayError("The gateway credential is missing or invalid. Configure ANTHROPIC_AUTH_TOKEN for the local gateway.", { status: 401, type: "authentication_error", code: "local_auth_failed" });
}

function requestMethodAllowed(request, response) {
  if (request.method === "OPTIONS") {
    response.writeHead(204, { "access-control-allow-methods": "GET, HEAD, POST, OPTIONS", "access-control-allow-headers": "authorization, content-type, x-api-key, anthropic-version, anthropic-beta", "access-control-max-age": "600" });
    response.end();
    return false;
  }
  if (!SAFE_METHODS.has(request.method)) return true;
  return true;
}

async function readJsonRequest(request, limitBytes) {
  let size = 0;
  const chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > limitBytes) {
      request.resume();
      throw new GatewayError(`Request body exceeds the configured ${limitBytes} byte limit.`, { status: 413, type: "request_too_large", code: "request_too_large" });
    }
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString("utf8");
  try { return JSON.parse(text); }
  catch { throw new GatewayError("Request body must be valid JSON.", { status: 400, type: "invalid_request_error", code: "invalid_json" }); }
}

async function readBodyLimited(body, limitBytes) {
  if (!body) return "";
  const reader = body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limitBytes) {
        await reader.cancel();
        throw new UpstreamProtocolError("Upstream response exceeded the configured response-size guard.");
      }
      chunks.push(Buffer.from(value));
    }
    return Buffer.concat(chunks).toString("utf8");
  } finally {
    try { reader.releaseLock(); } catch { /* already released */ }
  }
}

function sendJson(response, status, body, requestId, extraHeaders = {}) {
  if (response.headersSent || response.destroyed) return;
  const serialized = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(serialized),
    "cache-control": "no-store",
    "x-request-id": requestId,
    ...extraHeaders
  });
  response.end(serialized);
}

function anthropicClientModelList(config) {
  const ids = [...new Set([...Object.keys(config.modelMap), ...(config.defaultModel ? [config.defaultModel] : [])])];
  const data = ids.map(id => ({ type: "model", id, display_name: id, description: "Configured gateway model route" }));
  return { data, has_more: false, first_id: data[0]?.id ?? null, last_id: data.at(-1)?.id ?? null };
}

function upstreamRequestHeaders(config, streaming) {
  const headers = { "content-type": "application/json", accept: streaming ? "text/event-stream" : "application/json", "user-agent": "openai-compatible-claude-gateway/0.1.0" };
  if (config.upstreamApiKey) headers.authorization = `Bearer ${config.upstreamApiKey}`;
  return headers;
}

async function callUpstream(config, translated, controller, requestId) {
  let upstreamResponse;
  try {
    upstreamResponse = await fetch(config.upstreamUrl, {
      method: "POST",
      headers: upstreamRequestHeaders(config, translated.request.stream),
      body: JSON.stringify(translated.request),
      signal: controller.signal,
      redirect: "error"
    });
  } catch (cause) {
    if (controller.signal.aborted && controller.signal.reason instanceof UpstreamError) throw controller.signal.reason;
    throw new UpstreamError("Could not connect to the configured OpenAI-compatible upstream. Verify DNS, TLS, endpoint reachability, and request timeout settings.", { status: 502, type: "api_error", code: "upstream_connection_failed", cause });
  }
  if (!upstreamResponse.ok) {
    const error = publicUpstreamError(upstreamResponse.status, upstreamResponse.headers.get("retry-after") || undefined);
    try { await upstreamResponse.body?.cancel(); } catch { /* best-effort drain */ }
    throw error;
  }
  if (translated.request.stream) {
    const contentType = upstreamResponse.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("text/event-stream")) {
      try { await upstreamResponse.body?.cancel(); } catch { /* best effort */ }
      throw new UpstreamProtocolError("Upstream was asked to stream but did not return Content-Type: text/event-stream. Enable streaming only for a provider endpoint that supports SSE.");
    }
    return upstreamResponse;
  }
  let text;
  try { text = await readBodyLimited(upstreamResponse.body, Math.max(config.maxBodyBytes * 4, 8 * 1024 * 1024)); }
  catch (cause) { if (cause instanceof UpstreamProtocolError) throw cause; throw new UpstreamProtocolError("Failed while reading the upstream JSON response.", cause); }
  let payload;
  try { payload = JSON.parse(text); }
  catch (cause) { throw new UpstreamProtocolError("Upstream returned invalid JSON for a non-streaming Chat Completions request.", cause); }
  return { payload, requestId };
}

function mapError(error) {
  if (error instanceof GatewayError || error instanceof UpstreamError) return error;
  if (error && Number.isInteger(error.status) && typeof error.type === "string" && typeof error.message === "string") return error;
  return new GatewayError("The gateway encountered an unexpected internal error. Check the redacted gateway logs using the response request ID.", { status: 500, type: "api_error", code: "internal_error", cause: error });
}

function logSafeError(requestId, error, minimumLevel = "info") {
  const candidate = mapError(error);
  logEvent("error", "request_failed", { request_id: requestId, code: candidate.code || candidate.name || "error", status: candidate.status || 500 }, minimumLevel);
}

export function createGatewayServer(config) {
  const activeControllers = new Set();
  let activeRequests = 0;
  const server = http.createServer(async (request, response) => {
    const requestId = randomUUID();
    response.setHeader("x-content-type-options", "nosniff");
    response.setHeader("referrer-policy", "no-referrer");
    // No Access-Control-Allow-Origin header is emitted: browser cross-origin access is denied by default.
    let route;
    try { route = new URL(request.url || "/", "http://gateway.invalid").pathname; }
    catch { sendJson(response, 400, { type: "error", error: { type: "invalid_request_error", message: "Invalid request URL." } }, requestId); return; }

    if (request.method === "HEAD" && route === "/api/hello") { response.writeHead(204, { "x-request-id": requestId }); response.end(); return; }
    if ((request.method === "GET" || request.method === "HEAD") && route === "/health") {
      if (request.method === "HEAD") { response.writeHead(200, { "x-request-id": requestId }); response.end(); return; }
      sendJson(response, 200, { status: "ok" }, requestId); return;
    }
    if ((request.method === "GET" || request.method === "HEAD") && route === "/") {
      const body = { service: "openai-compatible-claude-gateway", status: "ok", endpoints: ["POST /v1/messages", "GET /v1/models", "GET /health"] };
      if (request.method === "HEAD") { response.writeHead(200, { "x-request-id": requestId }); response.end(); return; }
      sendJson(response, 200, body, requestId); return;
    }

    if (!requestMethodAllowed(request, response)) return;
    if (route !== "/v1/messages" && route !== "/v1/models" && route !== "/v1/messages/count_tokens") {
      sendJson(response, 404, { type: "error", error: { type: "not_found_error", message: "Route not found." } }, requestId); return;
    }
    try { requireLocalAuth(request, config); }
    catch (error) { const mapped = mapError(error); sendJson(response, mapped.status, anthropicError(mapped, requestId), requestId); return; }

    if (request.method === "GET" && route === "/v1/models") {
      const body = anthropicClientModelList(config);
      sendJson(response, 200, body, requestId); return;
    }
    if (request.method === "POST" && route === "/v1/messages/count_tokens") {
      sendJson(response, 404, { type: "error", error: { type: "not_found_error", message: "Exact token counting is unavailable for generic Chat Completions. Claude Code's documented gateway behavior is to fall back to a character-based estimate when this optional endpoint is absent." }, request_id: requestId }, requestId); return;
    }
    if (request.method !== "POST" || route !== "/v1/messages") {
      sendJson(response, 405, { type: "error", error: { type: "invalid_request_error", message: "Method not allowed for this route." } }, requestId, { allow: route === "/v1/models" ? "GET" : "POST" }); return;
    }
    if (activeRequests >= config.maxConcurrentRequests) {
      sendJson(response, 429, { type: "error", error: { type: "rate_limit_error", message: "Gateway concurrency limit reached; retry after an active request completes." }, request_id: requestId }, requestId, { "retry-after": "1" }); return;
    }

    activeRequests++;
    let controller;
    let deadline;
    try {
      const body = await readJsonRequest(request, config.maxBodyBytes);
      const translated = translateAnthropicRequest(body, config);
      controller = new AbortController();
      activeControllers.add(controller);
      deadline = setTimeout(() => controller.abort(new UpstreamError(`Upstream request timed out after ${config.requestTimeoutMs} ms.`, { status: 504, type: "api_error", code: "upstream_request_timeout" })), config.requestTimeoutMs);
      deadline.unref?.();
      const abortOnClose = () => { if (!response.writableEnded && !controller.signal.aborted) controller.abort(new Error("Client disconnected")); };
      response.once("close", abortOnClose);
      request.once("aborted", abortOnClose);
      const upstream = await callUpstream(config, translated, controller, requestId);
      if (translated.request.stream) {
        response.writeHead(200, {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          connection: "keep-alive",
          "x-accel-buffering": "no",
          "x-request-id": requestId
        });
        await streamChatCompletion(upstream, {
          clientModel: translated.clientModel,
          streamIdleTimeoutMs: config.streamIdleTimeoutMs,
          signal: controller.signal,
          streamRequiresDone: config.capabilities.streamRequiresDone,
          toolCalling: config.capabilities.toolCalling
        }, response);
        if (!response.writableEnded && !response.destroyed) response.end();
        logEvent("info", "request_completed", { request_id: requestId, route, status: 200, streamed: true, upstream_status: upstream.status }, config.logLevel);
      } else {
        if (Array.isArray(upstream.payload?.choices?.[0]?.message?.tool_calls) && upstream.payload.choices[0].message.tool_calls.length && !config.capabilities.toolCalling) throw new UpstreamProtocolError("Upstream returned tool calls although tool calling is disabled for this model.");
        const anthropic = translateChatCompletionResponse(upstream.payload, translated.clientModel);
        sendJson(response, 200, anthropic, requestId);
        logEvent("info", "request_completed", { request_id: requestId, route, status: 200, streamed: false }, config.logLevel);
      }
    } catch (error) {
      if (controller?.signal.aborted && (response.destroyed || !response.writable)) {
        logEvent("info", "request_cancelled", { request_id: requestId, route }, config.logLevel);
        return;
      }
      const mapped = mapError(error);
      logSafeError(requestId, mapped, config.logLevel);
      if (response.headersSent) {
        if (!response.destroyed && !response.writableEnded) {
          try {
            await writeSse(response, "error", { type: "error", error: { type: mapped.type || "api_error", message: mapped.message }, request_id: requestId });
            response.end();
          } catch { response.destroy(); }
        }
      } else {
        const serialized = anthropicError(mapped, requestId);
        const retryAfter = mapped.retryAfter !== undefined && /^[0-9]{1,6}$/.test(String(mapped.retryAfter)) ? String(mapped.retryAfter) : undefined;
        const headers = retryAfter ? { "retry-after": retryAfter } : {};
        sendJson(response, mapped.status, serialized.body, requestId, headers);
      }
    } finally {
      if (deadline) clearTimeout(deadline);
      if (controller) activeControllers.delete(controller);
      activeRequests = Math.max(0, activeRequests - 1);
    }
  });

  server.on("clientError", (_error, socket) => {
    if (socket.writable) socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
  });
  server.setTimeout(0); // request and upstream timeouts are enforced explicitly.
  server.closeActiveGatewayRequests = () => {
    for (const controller of activeControllers) controller.abort(new Error("Gateway is shutting down"));
  };
  return server;
}

export function logStartup(config) {
  logEvent("info", "gateway_started", {
    host: config.host,
    port: config.port,
    upstream_endpoint: config.displayEndpoint,
    model_routing: config.defaultModel ? "default-model-with-alias-overrides" : "explicit-model-map",
    capabilities: config.capabilities,
    gateway_authentication: Boolean(config.gatewayApiKey),
    auto_mode_server_checks: "disabled by supported Claude Code launch wrappers; classifier requests are not promised free"
  }, config.logLevel);
  process.stdout.write("Auto Mode server checks: disabled by the supported launch wrappers for this OpenAI-compatible upstream; local classifier path selected (provider billing may apply).\n");
}
