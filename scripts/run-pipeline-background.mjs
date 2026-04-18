import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const cwd = process.cwd();
const dataDir = path.join(cwd, "data");
const statusPath = path.join(dataDir, "build-status.json");
const logPath = path.join(dataDir, "build.log");

await mkdir(dataDir, { recursive: true });

function timestamp() {
  return new Date().toISOString();
}

async function saveStatus(status) {
  await writeFile(statusPath, `${JSON.stringify(status, null, 2)}\n`, "utf-8");
}

await saveStatus({
  state: "running",
  summary: "Build is running in the background.",
  startedAt: timestamp(),
  finishedAt: null,
  logPath,
});

const child = spawn(process.execPath.includes("node") ? "python3" : "python3", ["pipeline.py", "--reset-index"], {
  cwd,
  env: process.env,
});

let output = "";

child.stdout.on("data", (chunk) => {
  output += chunk.toString();
});

child.stderr.on("data", (chunk) => {
  output += chunk.toString();
});

child.on("close", async (code) => {
  await writeFile(logPath, output, "utf-8");

  if (code === 0) {
    await saveStatus({
      state: "success",
      summary: "Build completed successfully.",
      startedAt: null,
      finishedAt: timestamp(),
      logPath,
    });
    process.exit(0);
  }

  const lastLine = output.trim().split("\n").filter(Boolean).at(-1) || "Build failed.";
  await saveStatus({
    state: "error",
    summary: lastLine,
    startedAt: null,
    finishedAt: timestamp(),
    logPath,
  });
  process.exit(code ?? 1);
});
