export class GatewayError extends Error {
  constructor(message, { status = 400, type = "invalid_request_error", code = "gateway_error", cause } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = "GatewayError";
    this.status = status;
    this.type = type;
    this.code = code;
  }
}

export class ConfigError extends Error {
  constructor(message, cause) {
    super(message, cause ? { cause } : undefined);
    this.name = "ConfigError";
  }
}

export class UpstreamError extends Error {
  constructor(message, { status = 502, type = "api_error", code = "upstream_error", retryAfter, cause } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = "UpstreamError";
    this.status = status;
    this.type = type;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

export class UpstreamProtocolError extends UpstreamError {
  constructor(message, cause) {
    super(message, { status: 502, type: "api_error", code: "upstream_protocol_error", cause });
    this.name = "UpstreamProtocolError";
  }
}

export function anthropicError(error, requestId) {
  const status = Number.isInteger(error?.status) ? error.status : 500;
  const type = typeof error?.type === "string" ? error.type : "api_error";
  const message = typeof error?.message === "string" ? error.message : "The gateway encountered an unexpected error.";
  return {
    status,
    body: {
      type: "error",
      error: { type, message },
      ...(requestId ? { request_id: requestId } : {})
    }
  };
}

export function sanitizeText(value, secrets = []) {
  let text = String(value ?? "");
  for (const secret of secrets) {
    if (typeof secret === "string" && secret.length >= 4) text = text.split(secret).join("[REDACTED]");
  }
  return text
    .replace(/\bBearer\s+[^\s,;]+/gi, "Bearer [REDACTED]")
    .replace(/(x-api-key|api[_-]?key|authorization|cookie)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]")
    .replace(/(https?:\/\/)[^/@\s]+:[^/@\s]+@/gi, "$1[REDACTED]@")
    .slice(0, 2000);
}

export function publicUpstreamError(status, retryAfter) {
  if (status === 400 || status === 422) return new UpstreamError(`The configured upstream rejected the translated request (HTTP ${status}); check provider-specific request compatibility.`, { status: 400, type: "invalid_request_error", code: "upstream_rejected_request" });
  if (status === 401 || status === 403) return new UpstreamError(`The configured upstream rejected its configured credentials (HTTP ${status}); verify OPENAI_COMPATIBLE_API_KEY and provider permissions.`, { status: 502, type: "api_error", code: "upstream_authentication_failed" });
  if (status === 404) return new UpstreamError("The configured upstream endpoint returned HTTP 404; verify OPENAI_COMPATIBLE_BASE_URL and OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH.", { status: 502, type: "api_error", code: "upstream_endpoint_not_found" });
  if (status === 413) return new UpstreamError("The upstream rejected the request as too large (HTTP 413); reduce the request size or context.", { status: 413, type: "request_too_large", code: "upstream_request_too_large" });
  if (status === 429) return new UpstreamError("The configured upstream rate-limited this request (HTTP 429).", { status: 429, type: "rate_limit_error", code: "upstream_rate_limited", retryAfter });
  if (status === 408 || status === 504) return new UpstreamError(`The upstream request timed out (HTTP ${status}).`, { status: 504, type: "api_error", code: "upstream_timeout" });
  if (status >= 500) return new UpstreamError(`The configured upstream failed with HTTP ${status}.`, { status: 502, type: "api_error", code: "upstream_server_error" });
  return new UpstreamError(`The configured upstream returned an unexpected HTTP status (${status}).`, { status: 502, type: "api_error", code: "upstream_http_error" });
}
