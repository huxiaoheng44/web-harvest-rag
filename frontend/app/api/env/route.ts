import { NextResponse } from "next/server";

import { FIXED_ENV_FIELDS, isValidEnvKey } from "@/lib/env-fields";
import { loadEnvEntries, saveEnvEntries } from "@/lib/env-config";

export const runtime = "nodejs";

// This route reads/writes the real .env file, including secrets like
// OPENAI_API_KEY and SUPABASE_SERVICE_ROLE_KEY - it has no auth and is only
// safe for local development, never a public deployment.
function disabledInProduction() {
  return process.env.NODE_ENV === "production"
    ? NextResponse.json({ error: "Not available" }, { status: 404 })
    : null;
}

export async function GET() {
  const disabled = disabledInProduction();
  if (disabled) return disabled;

  const payload = await loadEnvEntries();
  return NextResponse.json({ ...payload, fixedFields: FIXED_ENV_FIELDS });
}

export async function PUT(request: Request) {
  const disabled = disabledInProduction();
  if (disabled) return disabled;

  const body = await request.json().catch(() => null);
  const entries = Array.isArray(body?.entries) ? (body.entries as Array<{ key?: string; value?: string; isCustom?: boolean }>) : null;

  if (!entries) {
    return NextResponse.json({ error: "Entries are required" }, { status: 400 });
  }

  const invalid = entries.find((entry) => !entry?.key || !isValidEnvKey(String(entry.key).trim()));
  if (invalid) {
    return NextResponse.json({ error: `Invalid environment variable key: ${invalid.key || ""}` }, { status: 400 });
  }

  const payload = await saveEnvEntries(
    entries.map((entry) => ({
      key: String(entry.key).trim(),
      value: String(entry.value ?? ""),
      isCustom: Boolean(entry.isCustom),
    })),
  );

  return NextResponse.json({
    ...payload,
    fixedFields: FIXED_ENV_FIELDS,
    message: "Environment variables saved locally.",
  });
}
