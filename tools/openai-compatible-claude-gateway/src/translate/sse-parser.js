import { UpstreamError, UpstreamProtocolError } from "../errors.js";

async function readWithIdleTimeout(reader, idleTimeoutMs, signal) {
  let timer;
  let onAbort;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new UpstreamError(`Upstream stream was idle for ${idleTimeoutMs} ms.`, { status: 504, type: "api_error", code: "upstream_stream_idle_timeout" })), idleTimeoutMs);
    timer.unref?.();
  });
  const aborted = signal ? new Promise((_, reject) => {
    onAbort = () => reject(signal.reason || new Error("Request cancelled"));
    if (signal.aborted) onAbort();
    else signal.addEventListener("abort", onAbort, { once: true });
  }) : new Promise(() => {});
  try { return await Promise.race([reader.read(), timeout, aborted]); }
  finally {
    clearTimeout(timer);
    if (signal && onAbort) signal.removeEventListener("abort", onAbort);
  }
}

/** Incrementally parses SSE without assuming TCP chunks align with lines/events. */
export async function* parseSse(body, { idleTimeoutMs = 60_000, signal } = {}) {
  if (!body || typeof body.getReader !== "function") throw new UpstreamProtocolError("Upstream declared a stream but returned no readable response body.");
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let dataLines = [];
  let eventName = "";
  let sawDone = false;

  function dispatch() {
    if (!dataLines.length && !eventName) return null;
    const event = { event: eventName || "message", data: dataLines.join("\n") };
    dataLines = [];
    eventName = "";
    return event;
  }

  try {
    while (true) {
      const result = await readWithIdleTimeout(reader, idleTimeoutMs, signal);
      if (result.done) {
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(result.value, { stream: true });
      while (buffer.length) {
        const match = /[\r\n]/.exec(buffer);
        if (!match) break;
        const position = match.index;
        if (buffer[position] === "\r" && position === buffer.length - 1) break;
        const line = buffer.slice(0, position);
        const delimiterLength = buffer[position] === "\r" && buffer[position + 1] === "\n" ? 2 : 1;
        buffer = buffer.slice(position + delimiterLength);
        if (line === "") {
          const event = dispatch();
          if (event) {
            if (event.data === "[DONE]") { sawDone = true; yield { ...event, done: true }; return; }
            yield event;
          }
          continue;
        }
        if (line.startsWith(":")) { yield { event: "ping", data: "" }; continue; } // preserve provider keepalives for the client stream
        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        let value = colon < 0 ? "" : line.slice(colon + 1);
        if (value.startsWith(" ")) value = value.slice(1);
        if (field === "data") dataLines.push(value);
        else if (field === "event") eventName = value;
      }
    }
    if (buffer.length) {
      const line = buffer.replace(/\r$/, "");
      if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
      else if (line.startsWith("event:")) eventName = line.slice(6).replace(/^ /, "");
      else if (!line.startsWith(":")) throw new UpstreamProtocolError("Upstream SSE stream ended in the middle of a field line.");
    }
    const last = dispatch();
    if (last) {
      if (last.data === "[DONE]") { sawDone = true; yield { ...last, done: true }; }
      else yield last;
    }
  } catch (error) {
    try { await reader.cancel(error); } catch { /* best-effort stream cleanup */ }
    throw error;
  } finally {
    try { reader.releaseLock(); } catch { /* reader may already be released */ }
  }
  if (sawDone) return;
}
