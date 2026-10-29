# Protocol and field-mapping design

This document specifies the implemented bridge contract. It intentionally does not claim full Anthropic API fidelity or universal feature support.

## Request flow

1. Validate the local HTTP route, configured local credential, JSON body size, request deadline, model route and declared capabilities.
2. Resolve the upstream model: exact requested ID in `OPENAI_COMPATIBLE_MODEL_MAP`, otherwise `OPENAI_COMPATIBLE_MODEL`, otherwise explicitly enabled pass-through.
3. Translate only recognized request fields into a clean Chat Completions object. Never copy arbitrary inbound headers or raw request fields upstream.
4. Call only the configured endpoint with a fresh `Authorization: Bearer OPENAI_COMPATIBLE_API_KEY` header if configured. Redirects are errors. Client-provided URLs cannot alter upstream routing.
5. Convert the response to the Anthropic Messages JSON contract or stream each upstream SSE event incrementally into Anthropic SSE events.

## Request field mapping

| Anthropic field/content | Chat Completions mapping | Implemented policy |
|---|---|---|
| `model` | `model` | Alias → configured default → opt-in pass-through. The response uses the original client model label. |
| `system` string/text blocks | leading `system` message | Text preserved; non-text system blocks rejected. |
| `messages` roles and text | ordered `system`/`user`/`assistant` messages | Text order preserved. Unknown roles/content kinds rejected. |
| user image blocks | `image_url` text/image content parts | Only when `images=true`; base64 data URLs and unauthenticated HTTP(S) URLs supported. |
| assistant `tool_use` | assistant `tool_calls` | Tool IDs preserved; input JSON serialized. Multiple calls and parallel IDs are preserved. |
| user `tool_result` | `role: tool`, `tool_call_id`, content | Exact tool ID retained. Text and configured image parts accepted; `is_error=true` rejected because no interoperable marker exists. Mixing tool results with other user blocks is rejected to prevent reordering. |
| `max_tokens` | `max_tokens` or `max_completion_tokens` | Select via validated capability configuration. |
| `temperature`, `top_p`, stop sequences | `temperature`, `top_p`, `stop` | Passed only when capability is enabled; values validated. |
| `stream` | `stream` | Real upstream SSE is required; no buffering-to-completion substitute. `include_usage` requested when configured. |
| `tools`, `tool_choice` | function tools and `tool_choice` | `auto`, `any` → `required`, `none`, named function; local tool execution never occurs. |
| `output_config.format` | `response_format: json_schema` | Requires explicit `jsonSchema=true`; response schema behavior remains provider-dependent. |
| `effort` / `output_config.effort` | `reasoning_effort` | Only low/medium/high, and only with explicit `reasoningEffort=true`. This does not map Anthropic extended thinking. |
| metadata / cache control | consumed locally | Not forwarded; this adapter does not promise equivalent per-provider attribution/caching. |
| `thinking` except disabled | none | Rejected; no fabricated reasoning block. |
| `safeguards`, MCP servers, containers, context management, unknown fields | none | Rejected with stable Anthropic-shaped error; no silent data loss. |

## Response mapping

Each non-streaming response uses a gateway-generated `msg_` identifier rather than leaking a provider-specific `chatcmpl_` ID to the Anthropic client.

- `choices[0].message.content` text → Anthropic `text` block.
- `message.tool_calls` → `tool_use` blocks; argument strings must parse as JSON objects.
- `finish_reason=stop` → `end_turn`; `length` → `max_tokens`; tool-call completion → `tool_use`.
- Provider `usage.prompt_tokens`/`completion_tokens` → Anthropic numeric usage. Missing values are unknown sentinels, not estimates; count-token endpoint is intentionally absent.
- OpenAI refusal text is represented as text content, not as a gateway-authored safety verdict.
- A non-streaming response missing a choice/message or containing malformed tool JSON is a protocol error.
- Any upstream `safeguard_results` response extension is rejected rather than stripped while implying classifier compatibility. The adapter never creates safety verdicts.

## Stream mapping

The parser accepts arbitrary byte chunks, CRLF/LF, multiple events per chunk, comments/keepalives, multiline data fields and `[DONE]`. Upstream comments/keepalive events are translated to Anthropic `ping` events so they continue to count as stream activity at the client. Text deltas produce `content_block_start`/`content_block_delta`; each streamed function call is keyed by its upstream tool index and emitted as an Anthropic `tool_use` block with `input_json_delta` fragments. Function arguments are validated as a complete object before successful terminal events. The final sequence contains `content_block_stop` for every opened block, `message_delta` with a mapped stop reason/usage, then `message_stop`.

An upstream error before the gateway sends response headers returns a JSON Anthropic error with an appropriate status. After SSE headers have been sent, the adapter emits an Anthropic-shaped `event: error` and ends the stream instead of writing a second JSON response. It does not retry inference. `[DONE]` is required by default; an operator may disable that requirement only after verifying a provider that uses a documented different termination contract.

## Auto Mode boundary

The Anthropic classifier protocol relies on the actual `safeguards` request field and `safeguard_results` response semantics. Those are not represented by generic Chat Completions. The launcher selects `CLAUDE_CODE_AUTO_MODE_SERVER=0` for the child CLI, which opts into the client classifier path; the resulting requests may be billed normally. Server-side checks are neither simulated nor claimed.
