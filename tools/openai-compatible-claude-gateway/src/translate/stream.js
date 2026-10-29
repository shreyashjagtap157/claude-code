import { randomUUID } from "node:crypto";
import { parseSse } from "./sse-parser.js";
import { parseToolArguments, mapFinishReason } from "./response.js";
import { UpstreamProtocolError } from "../errors.js";

export function writeSse(response, event, data) {
  if (response.destroyed || response.writableEnded) throw new Error("Client disconnected while writing the stream.");
  const ok = response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  if (ok) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const onDrain = () => { cleanup(); resolve(); };
    const onClose = () => { cleanup(); reject(new Error("Client disconnected while waiting for stream backpressure.")); };
    const cleanup = () => { response.off("drain", onDrain); response.off("close", onClose); };
    response.once("drain", onDrain);
    response.once("close", onClose);
  });
}

function validDelta(delta) {
  return delta && typeof delta === "object" ? delta : {};
}

export async function streamChatCompletion(upstreamResponse, { clientModel, streamIdleTimeoutMs, signal, streamRequiresDone = true, toolCalling = false }, response) {
  const messageId = `msg_${randomUUID().replaceAll("-", "")}`;
  await writeSse(response, "message_start", {
    type: "message_start",
    message: { id: messageId, type: "message", role: "assistant", model: clientModel, content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 0, output_tokens: 0 } }
  });

  let nextBlockIndex = 0;
  const textBlocks = [];
  const toolStates = new Map();
  let finishReason = null;
  let usage = null;
  let sawDone = false;
  let sawChoiceFinish = false;
  let sawAnyChoice = false;
  let upstreamEventIndex = 0;

  const getTextBlock = async () => {
    let block = textBlocks.length ? textBlocks[textBlocks.length - 1] : null;
    if (!block || block.closed) {
      block = { index: nextBlockIndex++, text: "", closed: false };
      textBlocks.push(block);
      await writeSse(response, "content_block_start", { type: "content_block_start", index: block.index, content_block: { type: "text", text: "" } });
    }
    return block;
  };

  const ensureToolStarted = async state => {
    if (state.started || !state.id || !state.name) return;
    state.index = nextBlockIndex++;
    state.started = true;
    await writeSse(response, "content_block_start", {
      type: "content_block_start", index: state.index,
      content_block: { type: "tool_use", id: state.id, name: state.name, input: {} }
    });
    if (state.arguments.length) {
      await writeSse(response, "content_block_delta", { type: "content_block_delta", index: state.index, delta: { type: "input_json_delta", partial_json: state.arguments } });
    }
  };

  for await (const event of parseSse(upstreamResponse.body, { idleTimeoutMs: streamIdleTimeoutMs, signal })) {
    const currentEventIndex = upstreamEventIndex++;
    if (event.done || event.data === "[DONE]") { sawDone = true; break; }
    if (event.event === "error") throw new UpstreamProtocolError("Upstream emitted an SSE error event; inspect the provider's redacted server-side diagnostics.");
    let payload;
    try { payload = JSON.parse(event.data); }
    catch (cause) { throw new UpstreamProtocolError("Upstream SSE event contained invalid JSON.", cause); }
    if (payload?.error) throw new UpstreamProtocolError("Upstream reported an error in a streaming payload.");
    if (payload && typeof payload === "object" && Object.hasOwn(payload, "safeguard_results")) throw new UpstreamProtocolError("Upstream returned safeguard_results, but this gateway does not implement or qualify for Anthropic server-side classifier protocol.");
    if (payload.usage && typeof payload.usage === "object") usage = payload.usage;
    if (!Array.isArray(payload.choices)) continue;
    const choice = payload.choices.find(item => item && (item.index === undefined || item.index === 0)) || payload.choices[0];
    if (!choice) continue;
    sawAnyChoice = true;
    const delta = validDelta(choice.delta);
    if (typeof delta.content === "string" && delta.content.length) {
      const block = await getTextBlock();
      block.text += delta.content;
      await writeSse(response, "content_block_delta", { type: "content_block_delta", index: block.index, delta: { type: "text_delta", text: delta.content } });
    } else if (Array.isArray(delta.content)) {
      for (const part of delta.content) {
        if (part?.type !== "text" || typeof part.text !== "string") throw new UpstreamProtocolError("Upstream stream returned an unsupported assistant content part.");
        if (part.text) {
          const block = await getTextBlock();
          block.text += part.text;
          await writeSse(response, "content_block_delta", { type: "content_block_delta", index: block.index, delta: { type: "text_delta", text: part.text } });
        }
      }
    }
    if (Array.isArray(delta.tool_calls)) {
      if (delta.tool_calls.length && !toolCalling) throw new UpstreamProtocolError("Upstream returned tool calls although tool calling is disabled for this model.");
      for (const toolDelta of delta.tool_calls) {
        if (!Number.isInteger(toolDelta?.index) || toolDelta.index < 0) throw new UpstreamProtocolError("Upstream tool-call delta has no valid index.");
        let state = toolStates.get(toolDelta.index);
        if (!state) {
          state = { upstreamIndex: toolDelta.index, id: null, name: "", arguments: "", started: false, index: -1, lastNameEvent: -1, lastArgumentsEvent: -1 };
          toolStates.set(toolDelta.index, state);
        }
        if (toolDelta.id) {
          if (state.id && state.id !== toolDelta.id) throw new UpstreamProtocolError("Upstream changed a tool-call ID after streaming had started.");
          state.id = toolDelta.id;
        }
        const fn = toolDelta.function || {};
        if (typeof fn.name === "string") {
          if (state.started && fn.name) throw new UpstreamProtocolError("Upstream continued changing a function name after the tool block had started.");
          state.name += fn.name;
          state.lastNameEvent = currentEventIndex;
        }
        if (fn.arguments !== undefined) {
          if (typeof fn.arguments !== "string") throw new UpstreamProtocolError("Upstream function arguments delta must be a string.");
          state.arguments += fn.arguments;
          state.lastArgumentsEvent = currentEventIndex;
          if (state.started && fn.arguments) await writeSse(response, "content_block_delta", { type: "content_block_delta", index: state.index, delta: { type: "input_json_delta", partial_json: fn.arguments } });
        }
      }
    }
    // A function name may arrive across several deltas; wait until arguments arrive after its final fragment.
    for (const state of toolStates.values()) {
      if (!state.started && state.id && state.name && state.lastArgumentsEvent >= 0 && (currentEventIndex > state.lastNameEvent || (choice.finish_reason !== undefined && choice.finish_reason !== null))) {
        await ensureToolStarted(state);
      }
    }
    if (choice.finish_reason !== undefined && choice.finish_reason !== null) {
      finishReason = choice.finish_reason;
      sawChoiceFinish = true;
    }
  }

  if (streamRequiresDone && !sawDone) throw new UpstreamProtocolError("Upstream SSE stream ended without the required [DONE] marker.");
  if (!sawAnyChoice) throw new UpstreamProtocolError("Upstream SSE stream completed without any choice data.");
  for (const state of toolStates.values()) {
    if (!state.id || !state.name || !state.started) throw new UpstreamProtocolError("Upstream stream ended with an incomplete tool-call ID or function name.");
    parseToolArguments(state.arguments, state.name);
  }
  if (!sawChoiceFinish && streamRequiresDone) throw new UpstreamProtocolError("Upstream stream ended without a final finish_reason.");

  const allBlocks = [
    ...textBlocks.map(block => ({ index: block.index, type: "text", state: block })),
    ...[...toolStates.values()].filter(state => state.started).map(state => ({ index: state.index, type: "tool_use", state }))
  ].sort((a, b) => a.index - b.index);
  for (const block of allBlocks) await writeSse(response, "content_block_stop", { type: "content_block_stop", index: block.index });

  const hasToolCalls = toolStates.size > 0;
  const inputTokens = Number.isInteger(usage?.prompt_tokens) && usage.prompt_tokens >= 0 ? usage.prompt_tokens : 0;
  const outputTokens = Number.isInteger(usage?.completion_tokens) && usage.completion_tokens >= 0 ? usage.completion_tokens : 0;
  await writeSse(response, "message_delta", { type: "message_delta", delta: { stop_reason: mapFinishReason(finishReason, hasToolCalls), stop_sequence: null }, usage: { output_tokens: outputTokens, input_tokens: inputTokens } });
  await writeSse(response, "message_stop", { type: "message_stop" });
}
