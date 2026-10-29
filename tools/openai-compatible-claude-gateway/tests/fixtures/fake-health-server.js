import http from "node:http";

const server = http.createServer((_request, response) => {
  response.writeHead(200, { "content-type": "application/json; charset=utf-8" });
  response.end(JSON.stringify({ status: "ok" }));
});
server.listen(0, "127.0.0.1", () => {
  process.stdout.write(String(server.address().port) + "\n");
});
