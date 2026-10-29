import { loadConfig } from "./config.js";
import { createGatewayServer, logStartup } from "./server.js";
import { ConfigError } from "./errors.js";

let config;
try { config = loadConfig(); }
catch (error) {
  const message = error instanceof ConfigError ? error.message : "Configuration failed validation.";
  process.stderr.write(`Configuration error: ${message}\n`);
  process.exitCode = 2;
  process.exit();
}

const server = createGatewayServer(config);
let shuttingDown = false;

server.on("error", error => {
  if (error.code === "EADDRINUSE") {
    process.stderr.write(`Gateway could not listen on ${config.host}:${config.port}: the port is already in use. No process was stopped. Set GATEWAY_PORT to an unused port and relaunch.\n`);
    process.exitCode = 1;
  } else {
    process.stderr.write(`Gateway server error (${error.code || error.name || "unknown"}).\n`);
    process.exitCode = 1;
  }
  if (!server.listening) process.exit();
});

server.listen(config.port, config.host, () => logStartup(config));

function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  process.stdout.write(`${signal} received; closing gateway and cancelling active upstream requests.\n`);
  server.closeActiveGatewayRequests();
  server.close(error => {
    if (error) {
      process.stderr.write("Gateway shutdown completed with a server-close error.\n");
      process.exitCode = 1;
    }
    process.exit();
  });
  const forced = setTimeout(() => process.exit(1), 5000);
  forced.unref?.();
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
