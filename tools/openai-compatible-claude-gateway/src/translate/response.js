import { randomUUID } from "node:crypto";
import { UpstreamProtocolError } from "../errors.js";

function stopReason(finishReason, hasToolCalls) {
  if (hasToolCalls || finishReason === "tool_calls" || finishReason === "function_call") return "tool_use";
  if (finishReason === "length" || finishReason === "max_tokens") return "max_tokens";
  return "end_turn";
}

function contentText(content) {
  if (content === null || content === undefined) return "";
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) throw new UpstreamProtocolError("Upstream message content has an unsupported type.");
  let result = "";
  for (const part of content) {
    if (part?.type === "text" && typeof part.text === "string") result += part.text;
    else throw new UpstreamProtocolError(`Upstream returned unsupported content part \"${String(part?.type)}\".`);
  }
  return result;
}

function parsedToolInput(call) {
  const name = call?.function?.name;
  const id = call?.id;
  if (typeof id !== "string" || !id || typeof name !== "string" || !name) throw new UpstreamProtocolError("Upstream returned a tool call without a stable ID or function name.");
  const raw = call.function.arguments;
  if (typeof raw !== "string") throw new UpstreamProtocolError(`Upstream tool call \"${name}\" arguments were not a JSON string.`);
  let input;
  try { input = JSON.parse(raw); }
  catch (cause) { throw new UpstreamProtocolError(`Upstream tool call \"${name}\" returned malformed JSON arguments.`, cause); }
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new UpstreamProtocolError(`Upstream tool call \"${name}\" arguments must decode to a JSON object.`);
  return { type: "tool_use", id, name, input };
}

export function translateChatCompletionResponse(upstream, clientModel) {
  if (upstream && typeof upstream === "object" && Object.hasOwn(upstream, "safeguard_results")) {
    throw new UpstreamProtocolError("Upstream returned safeguard_results, but this gateway does not implement or qualify for Anthropic server-side classifier protocol.");
  }
  if (!upstream || typeof upstream !== "object" || !Array.isArray(upstream.choices) || !upstream.choices.length) throw new UpstreamProtocolError("Upstream Chat Completions response did not contain choices.");
  const choice = upstream.choices.find(item => item && (item.index === undefined || item.index === 0)) || upstream.choices[0];
  if (!choice || !choice.message || typeof choice.message !== "object") throw new UpstreamProtocolError("Upstream response choice did not contain a message.");
  const content = [];
  const text = contentText(choice.message.content);
  if (text !== "") content.push({ type: "text", text });
  if (typeof choice.message.refusal === "string" && choice.message.refusal) content.push({ type: "text", text: choice.message.refusal });
  for (const call of choice.message.tool_calls || []) content.push(parsedToolInput(call));
  const usage = upstream.usage && typeof upstream.usage === "object" ? upstream.usage : null;
  const inputTokens = Number.isInteger(usage?.prompt_tokens) && usage.prompt_tokens >= 0 ? usage.prompt_tokens : 0;
  const outputTokens = Number.isInteger(usage?.completion_tokens) && usage.completion_tokens >= 0 ? usage.completion_tokens : 0;
  return {
    id: typeof upstream.id === "string" && upstream.id ? upstream.id : `msg_${randomUUID().replaceAll("-", "")}`,
    type: "message",
    role: "assistant",
    model: clientModel,
    content,
    stop_reason: stopReason(choice.finish_reason, content.some(block => block.type === "tool_use")),
    stop_sequence: null,
    usage: { input_tokens: inputTokens, output_tokens: outputTokens }
  };
}

export function mapFinishReason(finishReason, hasToolCalls) {
  return stopReason(finishReason, hasToolCalls);
}

export function parseToolArguments(raw, name = "tool") {
  let input;
  try { input = JSON.parse(raw); }
  catch (cause) { throw new UpstreamProtocolError(`Upstream tool call \"${name}\" completed with malformed JSON arguments.`, cause); }
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new UpstreamProtocolError(`Upstream tool call \"${name}\" arguments must decode to a JSON object.`);
  return input;
}
