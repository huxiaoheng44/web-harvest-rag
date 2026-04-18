import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { promises as fs } from "fs";

import { addSourcesFromText, loadSourcesConfig, removeSourceById } from "@/lib/source-config";
import { BUILD_LOG_PATH, readBuildStatus, writeBuildStatus } from "@/lib/build-status";
import { getAuthenticatedServerContext } from "@/lib/supabase/request-user";

export const runtime = "nodejs";

async function requireUser() {
  const { user } = await getAuthenticatedServerContext();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return null;
}

async function startPipelineBuild() {
  const current = await readBuildStatus();
  if (current.state === "running") {
    return false;
  }

  await fs.mkdir(process.cwd() + "/data", { recursive: true });
  await fs.writeFile(BUILD_LOG_PATH, "", "utf-8");
  await writeBuildStatus({
    state: "running",
    summary: "Build is running in the background.",
    startedAt: new Date().toISOString(),
    finishedAt: null,
    logPath: BUILD_LOG_PATH,
  });

  const child = spawn(process.execPath, ["scripts/run-pipeline-background.mjs"], {
    cwd: process.cwd(),
    env: process.env,
    detached: true,
    stdio: "ignore",
  });
  child.unref();
  return true;
}

export async function GET() {
  const authError = await requireUser();
  if (authError) {
    return authError;
  }

  const payload = await loadSourcesConfig();
  const buildStatus = await readBuildStatus();
  return NextResponse.json({ ...payload, buildStatus });
}

export async function POST(request: Request) {
  const authError = await requireUser();
  if (authError) {
    return authError;
  }

  const body = await request.json().catch(() => null);
  const text = body?.text?.trim();
  const runIngestion = Boolean(body?.runIngestion);

  if (!text) {
    return NextResponse.json({ error: "Paste one or more URLs first" }, { status: 400 });
  }

  const result = await addSourcesFromText(text);

  if (!result.added.length && !runIngestion) {
    return NextResponse.json({
      ...result,
      message: "No new URLs were added",
    });
  }

  if (!runIngestion) {
    const buildStatus = await readBuildStatus();
    return NextResponse.json({
      ...result,
      message: `Added ${result.added.length} source${result.added.length === 1 ? "" : "s"}`,
      buildStatus,
    });
  }

  const started = await startPipelineBuild();
  const buildStatus = await readBuildStatus();

  return NextResponse.json({
    ...result,
    message: started
      ? `Added ${result.added.length} source${result.added.length === 1 ? "" : "s"}. Build started in the background.`
      : "Build is already running in the background.",
    buildStatus,
  });
}

export async function PATCH() {
  const authError = await requireUser();
  if (authError) {
    return authError;
  }

  const started = await startPipelineBuild();
  const buildStatus = await readBuildStatus();
  return NextResponse.json({
    message: started ? "Build started in the background." : "Build is already running.",
    buildStatus,
  });
}

export async function DELETE(request: Request) {
  const authError = await requireUser();
  if (authError) {
    return authError;
  }

  const body = await request.json().catch(() => null);
  const id = body?.id?.trim();

  if (!id) {
    return NextResponse.json({ error: "Source id is required" }, { status: 400 });
  }

  const result = await removeSourceById(id);
  if (!result.removed) {
    return NextResponse.json({ error: "Source not found" }, { status: 404 });
  }

  const buildStatus = await readBuildStatus();
  return NextResponse.json({
    ...result,
    message: `Removed source: ${result.removed.title}`,
    buildStatus,
  });
}
