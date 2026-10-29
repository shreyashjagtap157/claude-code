import test from "node:test";
import assert from "node:assert/strict";
import { parseSse } from "../src/translate/sse-parser.js";

function streamFromChunks(chunks) {
  let index = 0;
  return new ReadableStream({ pull(controller) { if (index >= chunks.length) { controller.close(); return; } controller.enqueue(new TextEncoder().encode(chunks[index++])); } });
}

test("incremental SSE parser handles arbitrary chunks, CRLF/LF, comments, multiple data lines and DONE", async () => {
  const input = [": keepalive\r", "\n", "event: message\r\ndata: {\"value\":\r", "\n", "data: \"ok\"}\r\n\r", "\ndata: [DONE]\r\n\r\n"];
  const events = []; for await (const event of parseSse(streamFromChunks(input))) events.push(event);
  assert.deepEqual(events, [{ event: "message", data: '{"value":\n"ok"}' }, { event: "message", data: "[DONE]", done: true }]);
});

test("SSE parser treats a clean EOF without DONE as EOF, so the stream protocol layer can reject it", async () => {
  const events = []; for await (const event of parseSse(streamFromChunks(['data: {"choices":[]}\n\n']))) events.push(event);
  assert.equal(events.length, 1); assert.equal(events[0].data, '{"choices":[]}');
});

test("SSE parser dispatches a final unterminated data line at EOF", async () => {
  const events = []; for await (const event of parseSse(streamFromChunks(['data: {"x": 1']))) events.push(event);
  assert.deepEqual(events, [{ event: "message", data: '{"x": 1' }]);
});
