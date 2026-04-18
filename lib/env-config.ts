import { promises as fs } from "fs";
import path from "path";

import { FIXED_ENV_FIELDS, isValidEnvKey } from "@/lib/env-fields";

export type EnvEntry = {
  key: string;
  value: string;
  isCustom: boolean;
};

const ENV_PATH = path.join(process.cwd(), ".env");

function parseEnv(raw: string) {
  const entries = new Map<string, string>();

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const separator = trimmed.indexOf("=");
    if (separator === -1) {
      continue;
    }

    const key = trimmed.slice(0, separator).trim();
    let value = trimmed.slice(separator + 1);
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (isValidEnvKey(key)) {
      entries.set(key, value);
    }
  }

  return entries;
}

function quoteIfNeeded(value: string) {
  return /\s|#|"/.test(value) ? JSON.stringify(value) : value;
}

export async function loadEnvEntries() {
  let raw = "";
  try {
    raw = await fs.readFile(ENV_PATH, "utf-8");
  } catch {
    raw = "";
  }

  const parsed = parseEnv(raw);
  const fixedKeys = new Set(FIXED_ENV_FIELDS.map((field) => field.key));

  const fixedEntries: EnvEntry[] = FIXED_ENV_FIELDS.map((field) => ({
    key: field.key,
    value: parsed.get(field.key) ?? field.defaultValue ?? "",
    isCustom: false,
  }));

  const customEntries: EnvEntry[] = Array.from(parsed.entries())
    .filter(([key]) => !fixedKeys.has(key))
    .map(([key, value]) => ({ key, value, isCustom: true }));

  const missingRequired = fixedEntries
    .filter((entry) => !entry.value.trim() && !FIXED_ENV_FIELDS.find((field) => field.key === entry.key)?.defaultValue)
    .map((entry) => entry.key);

  return { entries: [...fixedEntries, ...customEntries], missingRequired };
}

export async function saveEnvEntries(entries: EnvEntry[]) {
  const normalized = entries
    .map((entry) => ({
      key: entry.key.trim(),
      value: entry.value ?? "",
      isCustom: entry.isCustom,
    }))
    .filter((entry) => entry.key && isValidEnvKey(entry.key));

  const fixedOrder = FIXED_ENV_FIELDS.map((field) => field.key);
  const fixedMap = new Map(normalized.filter((entry) => fixedOrder.includes(entry.key)).map((entry) => [entry.key, entry.value]));
  const customEntries = normalized.filter((entry) => !fixedOrder.includes(entry.key));

  const lines: string[] = [];
  for (const key of fixedOrder) {
    const value = fixedMap.get(key) ?? FIXED_ENV_FIELDS.find((field) => field.key === key)?.defaultValue ?? "";
    lines.push(`${key}=${quoteIfNeeded(value)}`);
  }

  if (customEntries.length) {
    lines.push("");
    for (const entry of customEntries) {
      lines.push(`${entry.key}=${quoteIfNeeded(entry.value)}`);
    }
  }

  await fs.writeFile(ENV_PATH, `${lines.join("\n")}\n`, "utf-8");

  const nextKeys = new Set(normalized.map((entry) => entry.key));
  for (const field of FIXED_ENV_FIELDS) {
    process.env[field.key] = fixedMap.get(field.key) ?? field.defaultValue ?? "";
  }
  for (const entry of customEntries) {
    process.env[entry.key] = entry.value;
  }

  return loadEnvEntries();
}
