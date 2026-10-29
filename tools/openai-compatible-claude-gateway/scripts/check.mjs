import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const sourceRoots = ["src", "scripts", "tests"];
const files = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (/\.(?:js|mjs)$/.test(entry.name)) files.push(file);
  }
}
for (const directory of sourceRoots) walk(path.join(root, directory));
let failed = false;
for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], { encoding: "utf8" });
  if (result.status !== 0) {
    failed = true;
    process.stderr.write(`${path.relative(root, file)}: ${result.stderr || result.stdout}`);
  }
}
if (failed) process.exit(1);
process.stdout.write(`Syntax check passed for ${files.length} JavaScript files. No external linter or type checker is configured (runtime is dependency-free JavaScript).\n`);
