import { GatewayError } from "../errors.js";
import { resolveModel } from "../config.js";

const KNOWN_TOP_LEVEL = new Set([
  "model", "messages", "system", "max_tokens", "temperature", "top_p", "stop_sequences", "stream", "tools", "tool_choice", "metadata", "output_config", "thinking", "effort", "cache_control", "context_management", "mcp_servers", "container", "service_tier", "disable_parallel_tool_use"
]);
const TEXT_BLOCK_TYPES = new Set(["text"]);

function invalid(message, code = "invalid_request") {
  return new GatewayError(message, { status: 400, type: "invalid_request_error", code });
}

function textOnlyContent(value, where) {
  if (typeof value === "string") return value;
  if (!Array.isArray(value)) throw invalid(`${where} must be a string or an array of text blocks.`);
  const output = [];
  for (const block of value) {
    if (!block || typeof block !== "object" || !TEXT_BLOCK_TYPES.has(block.type)) {
      throw invalid(`${where} contains unsupported content block${block?.type ? ` \"${block.type}\"` : ""}; only text blocks are supported here.`);
    }
    if (typeof block.text !== "string") throw invalid(`${where} contains a text block without a string text value.`);
    output.push(block.text);
  }
  return output.join("");
}

function imagePart(block, capabilities, where) {
  if (!capabilities.images) throw invalid(`${where} contains an image, but images are disabled for this upstream. Set OPENAI_COMPATIBLE_CAPABILITIES.images=true only after validating vision support.`, "unsupported_capability");
  const source = block.source;
  if (!source || typeof source !== "object") throw invalid(`${where} image block is missing source metadata.`);
  let url;
  if (source.type === "base64") {
    if (typeof source.media_type !== "string" || !/^image\/[A-Za-z0-9.+-]+$/.test(source.media_type)) throw invalid(`${where} image media_type must be a supported image MIME type.`);
    if (typeof source.data !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(source.data) || source.data.length % 4 === 1) throw invalid(`${where} image has invalid base64 data.`);
    url = `data:${source.media_type};base64,${source.data}`;
  } else if (source.type === "url") {
    if (typeof source.url !== "string") throw invalid(`${where} image URL must be a string.`);
    let parsed;
    try { parsed = new URL(source.url); } catch { throw invalid(`${where} image URL must be an absolute HTTP(S) URL.`); }
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) throw invalid(`${where} image URL must use HTTP(S) and must not embed credentials.`);
    url = source.url;
  } else {
    throw invalid(`${where} uses unsupported image source type \"${String(source.type)}\".`);
  }
  return { type: "image_url", image_url: { url } };
}

function parseUserBlocks(content, capabilities, where) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) throw invalid(`${where} content must be a string or content-block array.`);
  const parts = [];
  const extracted = [];
  for (const block of content) {
    if (!block || typeof block !== "object" || typeof block.type !== "string") throw invalid(`${where} contains a malformed content block.`);
    if (block.type === "text") {
      if (typeof block.text !== "string") throw invalid(`${where} contains a text block without a string text value.`);
      parts.push({ type: "text", text: block.text });
    } else if (block.type === "image") {
      parts.push(imagePart(block, capabilities, where));
    } else if (block.type === "tool_result") {
      const toolUseId = block.tool_use_id;
      if (typeof toolUseId !== "string" || !toolUseId) throw invalid(`${where} tool_result must include tool_use_id.`);
      if (block.is_error !== undefined && typeof block.is_error !== "boolean") throw invalid(`${where} tool_result is_error must be boolean.`);
      if (block.is_error === true) throw invalid(`${where} tool_result is_error has no generic Chat Completions equivalent and cannot be preserved faithfully.`, "unsupported_content");
      let resultContent;
      if (typeof block.content === "string") resultContent = block.content;
      else if (Array.isArray(block.content)) {
        const resultParts = [];
        let onlyText = true;
        for (const item of block.content) {
          if (item?.type === "text" && typeof item.text === "string") resultParts.push({ type: "text", text: item.text });
          else if (item?.type === "image") { resultParts.push(imagePart(item, capabilities, `${where} tool_result`)); onlyText = false; }
          else throw invalid(`${where} contains unsupported tool_result content kind \"${String(item?.type)}\".`, "unsupported_content");
        }
        resultContent = onlyText ? resultParts.map(part => part.text).join("") : resultParts;
      } else if (block.content === null || block.content === undefined) resultContent = "";
      else throw invalid(`${where} tool_result content must be string, text blocks, or empty.`);
      extracted.push({ type: "tool_result", toolUseId, content: resultContent, isError: Boolean(block.is_error) });
    } else if (block.type === "document" || block.type === "audio" || block.type === "video" || block.type === "thinking" || block.type === "redacted_thinking" || block.type === "tool_reference") {
      throw invalid(`${where} contains unsupported Anthropic content block \"${block.type}\" for generic Chat Completions.`, "unsupported_content");
    } else {
      throw invalid(`${where} contains unknown content block kind \"${block.type}\".`, "unsupported_content");
    }
  }
  if (parts.length && extracted.length) throw invalid(`${where} mixes tool_result blocks with other user content blocks; generic Chat Completions cannot preserve this mixed block order safely.`, "unsupported_content");
  const regularContent = parts.length === 0 ? "" : (parts.some(part => part.type === "image_url") ? parts : parts.map(part => part.text).join(""));
  return { regularContent, toolResults: extracted };
}

function parseTools(tools, toolChoice, capabilities, disableParallel) {
  if (tools !== undefined && !Array.isArray(tools)) throw invalid("tools must be an array.");
  if (tools?.length && !capabilities.toolCalling) throw invalid("This upstream has not been configured as tool-capable. Set OPENAI_COMPATIBLE_CAPABILITIES.toolCalling=true only after validating function calling for the selected model.", "unsupported_capability");
  const functionTools = (tools || []).map((tool, index) => {
    if (!tool || typeof tool !== "object" || typeof tool.name !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(tool.name)) throw invalid(`tools[${index}].name must be a valid function name (1-64 letters, digits, underscores, or hyphens).`);
    if (!tool.input_schema || typeof tool.input_schema !== "object" || Array.isArray(tool.input_schema) || tool.input_schema.type !== "object") throw invalid(`tools[${index}].input_schema must be a JSON Schema object with type: \"object\".`);
    if (tool.description !== undefined && typeof tool.description !== "string") throw invalid(`tools[${index}].description must be a string.`);
    return { type: "function", function: { name: tool.name, ...(tool.description ? { description: tool.description } : {}), parameters: tool.input_schema } };
  });
  if (new Set(functionTools.map(item => item.function.name)).size !== functionTools.length) throw invalid("tools contains duplicate function names.");
  if (toolChoice !== undefined && tools === undefined) throw invalid("tool_choice was provided without tools.");
  let choice;
  if (toolChoice !== undefined) {
    if (functionTools.length === 0) throw invalid("tool_choice requires at least one declared tool.");
    if (!toolChoice || typeof toolChoice !== "object" || typeof toolChoice.type !== "string") throw invalid("tool_choice must be an Anthropic tool-choice object.");
    if (toolChoice.type === "auto") choice = "auto";
    else if (toolChoice.type === "any") choice = "required";
    else if (toolChoice.type === "none") choice = "none";
    else if (toolChoice.type === "tool") {
      if (typeof toolChoice.name !== "string" || !functionTools.some(item => item.function.name === toolChoice.name)) throw invalid("tool_choice.type=tool must name one of the tools declared in the request.");
      choice = { type: "function", function: { name: toolChoice.name } };
    } else throw invalid(`Unsupported tool_choice type \"${toolChoice.type}\". Generic Chat Completions supports auto, required, and named function selection only.`, "unsupported_capability");
  }
  if (disableParallel && !capabilities.parallelToolCalls && functionTools.length > 1) {
    // The request explicitly forbids parallel use; the upstream's normal single-call flow preserves that restriction.
    return { functionTools, choice, parallel: false };
  }
  if (!disableParallel && functionTools.length > 1 && !capabilities.parallelToolCalls) {
    // Multiple declared tools are still legal; unsupported parallel execution is expressed to the provider as false.
    return { functionTools, choice, parallel: false };
  }
  return { functionTools, choice, parallel: !disableParallel && capabilities.parallelToolCalls };
}

function validateRequest(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) throw invalid("Request body must be a JSON object.");
  for (const key of Object.keys(body)) if (!KNOWN_TOP_LEVEL.has(key)) throw invalid(`Unsupported Anthropic Messages field \"${key}\". The gateway will not silently discard semantics it cannot translate.`, "unsupported_field");
  if (typeof body.model !== "string" || !body.model.trim()) throw invalid("model must be a non-empty string.");
  if (!Number.isSafeInteger(body.max_tokens) || body.max_tokens < 1) throw invalid("max_tokens must be a positive integer.");
  if (!Array.isArray(body.messages) || body.messages.length === 0) throw invalid("messages must be a non-empty array.");
  if (body.stream !== undefined && typeof body.stream !== "boolean") throw invalid("stream must be boolean.");
  for (const field of ["temperature", "top_p"]) {
    if (body[field] !== undefined && (typeof body[field] !== "number" || !Number.isFinite(body[field]) || body[field] < 0 || body[field] > 1)) throw invalid(`${field} must be a finite number between 0 and 1.`);
  }
  if (body.stop_sequences !== undefined && (!Array.isArray(body.stop_sequences) || body.stop_sequences.some(value => typeof value !== "string"))) throw invalid("stop_sequences must be an array of strings.");
  if (body.metadata !== undefined && (!body.metadata || typeof body.metadata !== "object" || Array.isArray(body.metadata))) throw invalid("metadata must be an object when provided.");
  if (body.context_management !== undefined) throw invalid("context_management is not supported by generic OpenAI Chat Completions; remove the field or use a compatible upstream.", "unsupported_capability");
  if (body.mcp_servers !== undefined) throw invalid("Anthropic MCP server configuration is not an inference request feature available through generic Chat Completions.", "unsupported_capability");
  if (body.container !== undefined) throw invalid("Anthropic container/code-execution requests cannot be represented by generic Chat Completions.", "unsupported_capability");
  if (body.service_tier !== undefined) throw invalid("service_tier is provider-specific and has no generic Chat Completions equivalent; remove it or configure a provider-specific extension.", "unsupported_capability");
  if (body.thinking !== undefined && body.thinking?.type !== "disabled") throw invalid("Anthropic extended thinking cannot be mapped faithfully to generic Chat Completions reasoning fields. Disable thinking or use an explicitly supported provider integration.", "unsupported_capability");
  if (body.effort !== undefined && !["low", "medium", "high"].includes(body.effort)) throw invalid("effort must be low, medium, or high.");
}

export function translateAnthropicRequest(body, config) {
  validateRequest(body);
  const model = resolveModel(body.model, config);
  const caps = config.capabilities;
  if (body.stream && !caps.streaming) throw invalid("Streaming is disabled for this upstream in OPENAI_COMPATIBLE_CAPABILITIES.", "unsupported_capability");
  if (body.temperature !== undefined && !caps.temperature) throw invalid("This upstream is not configured to support temperature.", "unsupported_capability");
  if (body.top_p !== undefined && !caps.topP) throw invalid("This upstream is not configured to support top_p.", "unsupported_capability");
  if (body.stop_sequences?.length && !caps.stopSequences) throw invalid("This upstream is not configured to support stop sequences.", "unsupported_capability");
  if (body.effort !== undefined && !caps.reasoningEffort) throw invalid("Reasoning effort is disabled for this upstream. Validate and enable reasoningEffort only when its provider-specific field mapping is correct.", "unsupported_capability");
  if (body.output_config?.format && !caps.jsonSchema) throw invalid("Structured JSON output is disabled for this upstream. Validate JSON schema output support before enabling OPENAI_COMPATIBLE_CAPABILITIES.jsonSchema.", "unsupported_capability");
  if (body.output_config !== undefined && (!body.output_config || typeof body.output_config !== "object" || Array.isArray(body.output_config))) throw invalid("output_config must be an object.");
  if (body.output_config?.format) {
    const format = body.output_config.format;
    if (format.type !== "json_schema" || !format.schema || typeof format.schema !== "object" || Array.isArray(format.schema)) throw invalid("output_config.format must be a json_schema format with an object schema.");
  }
  const messages = [];
  if (body.system !== undefined) {
    const systemText = textOnlyContent(body.system, "system");
    messages.push({ role: "system", content: systemText });
  }
  for (let index = 0; index < body.messages.length; index++) {
    const message = body.messages[index];
    if (!message || typeof message !== "object" || !["user", "assistant", "system"].includes(message.role)) {
      const actualRole = typeof message?.role === "string" ? JSON.stringify(message.role.slice(0, 48)) : String(typeof message?.role);
      throw invalid(`messages[${index}].role ${actualRole} is not supported; expected user, assistant, or system.`, "unsupported_message_role");
    }
    if (!Object.hasOwn(message, "content")) throw invalid(`messages[${index}] is missing content.`);
    if (message.role === "system") {
      // Claude Code can emit system-role entries inside messages while using a custom Anthropic base URL.
      // Preserve their position in the turn list instead of rejecting or hoisting the content.
      messages.push({ role: "system", content: textOnlyContent(message.content, `messages[${index}] system`) });
    } else if (message.role === "user") {
      const translated = parseUserBlocks(message.content, caps, `messages[${index}]`);
      if (typeof translated === "string") messages.push({ role: "user", content: translated });
      else {
        if (translated.regularContent !== "" || !translated.toolResults.length) messages.push({ role: "user", content: translated.regularContent });
        for (const result of translated.toolResults) {
          if (!caps.toolCalling) throw invalid("tool_result appeared but tool calling is disabled for this upstream.", "unsupported_capability");
          messages.push({ role: "tool", tool_call_id: result.toolUseId, content: result.content });
        }
      }
    } else {
      if (typeof message.content === "string") messages.push({ role: "assistant", content: message.content });
      else if (!Array.isArray(message.content)) throw invalid(`messages[${index}].content must be a string or block array.`);
      else {
        const text = [];
        const toolCalls = [];
        for (const block of message.content) {
          if (!block || typeof block !== "object" || typeof block.type !== "string") throw invalid(`messages[${index}] contains a malformed content block.`);
          if (block.type === "text") {
            if (typeof block.text !== "string") throw invalid(`messages[${index}] text block must contain a string.`);
            text.push(block.text);
          } else if (block.type === "tool_use") {
            if (!caps.toolCalling) throw invalid("tool_use appeared but tool calling is disabled for this upstream.", "unsupported_capability");
            if (typeof block.id !== "string" || !block.id || typeof block.name !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(block.name)) throw invalid(`messages[${index}] contains an invalid tool_use id or name.`);
            if (!block.input || typeof block.input !== "object" || Array.isArray(block.input)) throw invalid(`messages[${index}] tool_use input must be a JSON object.`);
            toolCalls.push({ id: block.id, type: "function", function: { name: block.name, arguments: JSON.stringify(block.input) } });
          } else if (block.type === "thinking" || block.type === "redacted_thinking") {
            throw invalid(`messages[${index}] contains unsupported ${block.type} content; generic Chat Completions cannot preserve it.`, "unsupported_content");
          } else throw invalid(`messages[${index}] contains unsupported assistant content block \"${block.type}\".`, "unsupported_content");
        }
        messages.push({ role: "assistant", content: text.length ? text.join("") : null, ...(toolCalls.length ? { tool_calls: toolCalls } : {}) });
      }
    }
  }
  const translatedTools = parseTools(body.tools, body.tool_choice, caps, body.disable_parallel_tool_use === true);
  if (body.disable_parallel_tool_use !== undefined && typeof body.disable_parallel_tool_use !== "boolean") throw invalid("disable_parallel_tool_use must be boolean.");
  if (body.output_config !== undefined && Object.keys(body.output_config).some(key => key !== "format" && key !== "effort")) throw invalid(`Unsupported output_config field \"${Object.keys(body.output_config).find(key => key !== "format" && key !== "effort")}\".`);
  const request = {
    model,
    messages,
    [caps.maxTokensField]: body.max_tokens,
    stream: body.stream === true
  };
  if (body.temperature !== undefined) request.temperature = body.temperature;
  if (body.top_p !== undefined) request.top_p = body.top_p;
  if (body.stop_sequences?.length) request.stop = body.stop_sequences;
  if (translatedTools.functionTools.length) request.tools = translatedTools.functionTools;
  if (translatedTools.choice !== undefined) request.tool_choice = translatedTools.choice;
  if (translatedTools.functionTools.length) request.parallel_tool_calls = translatedTools.parallel;
  if (body.effort !== undefined) request.reasoning_effort = body.effort;
  if (body.output_config?.effort !== undefined) {
    if (!caps.reasoningEffort || !["low", "medium", "high"].includes(body.output_config.effort)) throw invalid("output_config.effort requires configured reasoningEffort support and one of low, medium, or high.", "unsupported_capability");
    request.reasoning_effort = body.output_config.effort;
  }
  if (body.output_config?.format) {
    request.response_format = { type: "json_schema", json_schema: { name: "response", strict: true, schema: body.output_config.format.schema } };
  }
  if (body.stream && caps.streamUsage) request.stream_options = { include_usage: true };
  return { request, clientModel: body.model, upstreamModel: model };
}
