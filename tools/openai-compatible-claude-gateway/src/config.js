import fs from "node:fs";
import path from "node:path";
import { isIP } from "node:net";
import { ConfigError } from "./errors.js";

const DEFAULT_CAPABILITIES = Object.freeze({
  streaming: true,
  toolCalling: false,
  parallelToolCalls: false,
  images: false,
  jsonSchema: false,
  reasoningEffort: false,
  temperature: true,
  topP: true,
  stopSequences: true,
  streamUsage: true,
  streamRequiresDone: true,
  maxTokensField: "max_tokens"
});
const CAPABILITY_KEYS = new Set(Object.keys(DEFAULT_CAPABILITIES));

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  let content;
  try { content = fs.readFileSync(filePath, "utf8"); }
  catch (error) { throw new ConfigError(`Cannot read environment file ${path.basename(filePath)}: ${error.message}`); }
  const result = {};
  for (const [index, line] of content.split(/\r?\n/).entries()) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!match) throw new ConfigError(`Invalid .env syntax on line ${index + 1}. Expected KEY=value.`);
    let value = match[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    else value = value.replace(/\s+#.*$/, "");
    result[match[1]] = value;
  }
  return result;
}

function parseBoolean(value, name, fallback = false) {
  if (value === undefined || value === null || value === "") return fallback;
  if (["true", "1", "yes", "on"].includes(String(value).toLowerCase())) return true;
  if (["false", "0", "no", "off"].includes(String(value).toLowerCase())) return false;
  throw new ConfigError(`${name} must be true or false.`);
}

function positiveInteger(value, name, fallback, maximum = 2_147_483_647) {
  if (value === undefined || value === null || value === "") return fallback;
  if (!/^\d+$/.test(String(value))) throw new ConfigError(`${name} must be a positive integer.`);
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || parsed > maximum) throw new ConfigError(`${name} must be between 1 and ${maximum}.`);
  return parsed;
}

function parseJson(value, name, fallback) {
  if (value === undefined || value === null || value === "") return fallback;
  try { return JSON.parse(value); }
  catch { throw new ConfigError(`${name} must contain valid JSON.`); }
}

function isLoopback(hostname) {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (host === "localhost" || host.endsWith(".localhost") || host === "::1") return true;
  if (isIP(host) === 4) return host.startsWith("127.");
  return false;
}

function normalizeBaseAndEndpoint(raw, pathOverride, allowInsecureHttp) {
  let base;
  try { base = new URL(raw); }
  catch { throw new ConfigError("OPENAI_COMPATIBLE_BASE_URL must be an absolute, valid URL."); }
  if (!["http:", "https:"].includes(base.protocol)) throw new ConfigError("OPENAI_COMPATIBLE_BASE_URL must use http or https.");
  if (base.username || base.password) throw new ConfigError("Credentials must not be embedded in OPENAI_COMPATIBLE_BASE_URL; use OPENAI_COMPATIBLE_API_KEY instead.");
  if (base.hash) throw new ConfigError("OPENAI_COMPATIBLE_BASE_URL must not contain a URL fragment.");
  if (base.port && (!/^\d+$/.test(base.port) || Number(base.port) < 1 || Number(base.port) > 65535)) throw new ConfigError("OPENAI_COMPATIBLE_BASE_URL contains an invalid port.");
  if (base.protocol === "http:" && !isLoopback(base.hostname) && !allowInsecureHttp) throw new ConfigError("Non-loopback upstreams must use HTTPS. Set OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP=true only if you deliberately accept cleartext transport.");

  let pathname = base.pathname.replace(/\/{2,}/g, "/");
  if (!pathname.startsWith("/")) pathname = `/${pathname}`;
  pathname = pathname.replace(/\/+$/, "") || "";
  if (pathOverride) {
    if (!pathOverride.startsWith("/") || pathOverride.includes("?") || pathOverride.includes("#") || pathOverride.includes("\\")) throw new ConfigError("OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH must be an absolute URL pathname without query, fragment, or backslash.");
    if (!/\/chat\/completions\/?$/.test(pathOverride)) throw new ConfigError("OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH must end with /chat/completions.");
    pathname = pathOverride.replace(/\/{2,}/g, "/").replace(/\/+$/, "");
  } else if (/\/chat\/completions$/i.test(pathname)) {
    // Full endpoint supplied; use it exactly once.
  } else if (/\/v1$/i.test(pathname)) {
    pathname += "/chat/completions";
  } else {
    pathname += "/v1/chat/completions";
  }
  if (!pathname.startsWith("/")) pathname = `/${pathname}`;
  const upstreamUrl = new URL(base.toString());
  upstreamUrl.pathname = pathname;
  const modelsUrl = new URL(base.toString());
  modelsUrl.pathname = pathname.replace(/\/chat\/completions$/i, "/models");
  modelsUrl.hash = "";
  // Query parameters supplied on the base URL are preserved, but never logged.
  return { upstreamUrl, modelsUrl, loopback: isLoopback(base.hostname), baseOrigin: base.origin };
}

function validateModelMap(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ConfigError("OPENAI_COMPATIBLE_MODEL_MAP must be a JSON object of requested model IDs to upstream model IDs.");
  const result = Object.create(null);
  for (const [key, mapped] of Object.entries(value)) {
    if (!key.trim() || key.length > 256 || typeof mapped !== "string" || !mapped.trim() || mapped.length > 256 || /[\r\n]/.test(key + mapped)) throw new ConfigError("OPENAI_COMPATIBLE_MODEL_MAP must map non-empty model IDs to non-empty model IDs.");
    result[key] = mapped;
  }
  return Object.freeze(result);
}

function validateCapabilities(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ConfigError("OPENAI_COMPATIBLE_CAPABILITIES must be a JSON object.");
  for (const key of Object.keys(value)) if (!CAPABILITY_KEYS.has(key)) throw new ConfigError(`Unknown capability key: ${key}. Supported keys: ${[...CAPABILITY_KEYS].join(", ")}.`);
  const result = { ...DEFAULT_CAPABILITIES, ...value };
  for (const key of CAPABILITY_KEYS) {
    if (key === "maxTokensField") continue;
    if (typeof result[key] !== "boolean") throw new ConfigError(`OPENAI_COMPATIBLE_CAPABILITIES.${key} must be boolean.`);
  }
  if (!["max_tokens", "max_completion_tokens"].includes(result.maxTokensField)) throw new ConfigError("OPENAI_COMPATIBLE_CAPABILITIES.maxTokensField must be max_tokens or max_completion_tokens.");
  if (result.parallelToolCalls && !result.toolCalling) throw new ConfigError("parallelToolCalls=true requires toolCalling=true.");
  return Object.freeze(result);
}

export function loadConfig({ env = process.env, cwd = process.cwd() } = {}) {
  const envFile = env.GATEWAY_ENV_FILE || path.join(cwd, ".env");
  const fileEnv = parseEnvFile(envFile);
  const merged = { ...fileEnv, ...env };
  const requiredBaseUrl = merged.OPENAI_COMPATIBLE_BASE_URL;
  if (!requiredBaseUrl) throw new ConfigError("OPENAI_COMPATIBLE_BASE_URL is required. Copy .env.example to .env and configure your upstream endpoint.");

  const model = String(merged.OPENAI_COMPATIBLE_MODEL ?? "").trim();
  const modelMap = validateModelMap(parseJson(merged.OPENAI_COMPATIBLE_MODEL_MAP, "OPENAI_COMPATIBLE_MODEL_MAP", {}));
  if (!model && !Object.keys(modelMap).length && String(merged.OPENAI_COMPATIBLE_MODEL_PASSTHROUGH ?? "false").toLowerCase() !== "true") {
    throw new ConfigError("Set OPENAI_COMPATIBLE_MODEL or at least one OPENAI_COMPATIBLE_MODEL_MAP entry; pass-through model routing requires OPENAI_COMPATIBLE_MODEL_PASSTHROUGH=true.");
  }
  if (merged.OPENAI_COMPATIBLE_MODEL_PASSTHROUGH !== undefined && !["true", "false"].includes(String(merged.OPENAI_COMPATIBLE_MODEL_PASSTHROUGH).toLowerCase())) throw new ConfigError("OPENAI_COMPATIBLE_MODEL_PASSTHROUGH must be true or false.");

  const allowInsecureHttp = parseBoolean(merged.OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP, "OPENAI_COMPATIBLE_ALLOW_INSECURE_HTTP", false);
  const normalized = normalizeBaseAndEndpoint(String(requiredBaseUrl), String(merged.OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH ?? "").trim(), allowInsecureHttp);
  const host = String(merged.GATEWAY_HOST || "127.0.0.1").trim();
  if (!host || /[\s/\\]/.test(host)) throw new ConfigError("GATEWAY_HOST must be a hostname or IP address.");
  const port = positiveInteger(merged.GATEWAY_PORT, "GATEWAY_PORT", 3456, 65535);
  const gatewayApiKey = String(merged.GATEWAY_API_KEY ?? "");
  const allowRemote = parseBoolean(merged.GATEWAY_ALLOW_REMOTE, "GATEWAY_ALLOW_REMOTE", false);
  if (!isLoopback(host) && (!allowRemote || !gatewayApiKey)) throw new ConfigError("Non-loopback binding requires both GATEWAY_ALLOW_REMOTE=true and a non-empty GATEWAY_API_KEY.");
  const logLevel = String(merged.GATEWAY_LOG_LEVEL || "info").toLowerCase();
  if (!["debug", "info", "warn", "error", "silent"].includes(logLevel)) throw new ConfigError("GATEWAY_LOG_LEVEL must be debug, info, warn, error, or silent.");
  const capabilitiesValue = parseJson(merged.OPENAI_COMPATIBLE_CAPABILITIES, "OPENAI_COMPATIBLE_CAPABILITIES", {});
  const capabilities = validateCapabilities(capabilitiesValue);

  return Object.freeze({
    host, port, gatewayApiKey, allowRemote,
    upstreamApiKey: String(merged.OPENAI_COMPATIBLE_API_KEY ?? ""),
    defaultModel: model,
    modelMap,
    passThroughModel: String(merged.OPENAI_COMPATIBLE_MODEL_PASSTHROUGH ?? "false").toLowerCase() === "true",
    upstreamUrl: normalized.upstreamUrl,
    modelsUrl: normalized.modelsUrl,
    upstreamLoopback: normalized.loopback,
    capabilities,
    logLevel,
    requestTimeoutMs: positiveInteger(merged.GATEWAY_REQUEST_TIMEOUT_MS, "GATEWAY_REQUEST_TIMEOUT_MS", 600000, 2147483647),
    streamIdleTimeoutMs: positiveInteger(merged.GATEWAY_STREAM_IDLE_TIMEOUT_MS, "GATEWAY_STREAM_IDLE_TIMEOUT_MS", 60000, 2147483647),
    maxBodyBytes: positiveInteger(merged.GATEWAY_MAX_BODY_BYTES, "GATEWAY_MAX_BODY_BYTES", 2 * 1024 * 1024, 100 * 1024 * 1024),
    maxConcurrentRequests: positiveInteger(merged.GATEWAY_MAX_CONCURRENT_REQUESTS, "GATEWAY_MAX_CONCURRENT_REQUESTS", 32, 10000),
    envFile: path.basename(envFile),
    displayEndpoint: normalized.upstreamUrl.origin + normalized.upstreamUrl.pathname,
    baseOrigin: normalized.baseOrigin
  });
}

export function resolveModel(requestedModel, config) {
  if (Object.hasOwn(config.modelMap, requestedModel)) return config.modelMap[requestedModel];
  if (config.defaultModel) return config.defaultModel;
  if (config.passThroughModel) return requestedModel;
  throw new (class extends Error { constructor() { super(`No upstream model is configured for requested model "${requestedModel}". Add an exact OPENAI_COMPATIBLE_MODEL_MAP entry or set OPENAI_COMPATIBLE_MODEL.`); this.name = "ModelRoutingError"; this.status = 400; this.type = "invalid_request_error"; this.code = "model_not_configured"; } })();
}

export const configInternals = { isLoopback, normalizeBaseAndEndpoint, parseEnvFile, validateCapabilities, validateModelMap, DEFAULT_CAPABILITIES };
