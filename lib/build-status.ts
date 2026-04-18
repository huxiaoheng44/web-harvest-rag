import { promises as fs } from "fs";
import path from "path";

export type BuildState = "idle" | "running" | "success" | "error";

export type BuildStatus = {
  state: BuildState;
  summary: string;
  startedAt: string | null;
  finishedAt: string | null;
  logPath: string | null;
};

export const BUILD_STATUS_PATH = path.join(process.cwd(), "data", "build-status.json");
export const BUILD_LOG_PATH = path.join(process.cwd(), "data", "build.log");

const DEFAULT_STATUS: BuildStatus = {
  state: "idle",
  summary: "No build has run yet.",
  startedAt: null,
  finishedAt: null,
  logPath: null,
};

export async function readBuildStatus() {
  try {
    const raw = await fs.readFile(BUILD_STATUS_PATH, "utf-8");
    return { ...DEFAULT_STATUS, ...(JSON.parse(raw) as Partial<BuildStatus>) };
  } catch {
    return DEFAULT_STATUS;
  }
}

export async function writeBuildStatus(status: BuildStatus) {
  await fs.mkdir(path.dirname(BUILD_STATUS_PATH), { recursive: true });
  await fs.writeFile(BUILD_STATUS_PATH, `${JSON.stringify(status, null, 2)}\n`, "utf-8");
}
