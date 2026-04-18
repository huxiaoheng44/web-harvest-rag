import { promises as fs } from "fs";
import path from "path";

export type SourceKind = "html" | "pdf";

export type ManagedSource = {
  id: string;
  title: string;
  url: string;
  type: SourceKind;
  category: string;
};

type SourceConfigPayload = {
  name?: string;
  sources?: Array<string | { id?: string; title?: string; url: string; type?: string; category?: string }>;
};

const SOURCE_CONFIG_PATH = path.join(process.cwd(), "config", "sources.json");
const URL_REGEX = /https?:\/\/[^\s<>"]+/gi;

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function stripTrailingPunctuation(value: string) {
  return value.replace(/[),.;]+$/g, "");
}

function inferType(url: string): SourceKind {
  return /\.pdf($|[?#])|coredownload\.pdf|inline\.pdf/i.test(url) ? "pdf" : "html";
}

function inferCategory(type: SourceKind) {
  return type === "pdf" ? "downloads" : "website";
}

function inferTitle(url: string) {
  try {
    const parsed = new URL(url);
    const lastSegment = parsed.pathname.split("/").filter(Boolean).at(-1);
    const candidate = lastSegment?.replace(/\.pdf$/i, "") || parsed.hostname;
    return candidate
      .replace(/[-_]+/g, " ")
      .replace(/\s+/g, " ")
      .trim() || url;
  } catch {
    return url;
  }
}

function inferId(url: string, usedIds: Set<string>) {
  let base = "source";

  try {
    const parsed = new URL(url);
    const hostname = parsed.hostname.replace(/^www\./, "");
    const pathname = parsed.pathname.split("/").filter(Boolean).join("-");
    base = slugify([hostname, pathname].filter(Boolean).join("-")) || base;
  } catch {
    base = slugify(url) || base;
  }

  let nextId = base;
  let counter = 2;
  while (usedIds.has(nextId)) {
    nextId = `${base}-${counter}`;
    counter += 1;
  }
  usedIds.add(nextId);
  return nextId;
}

function normalizeEntry(
  entry: string | { id?: string; title?: string; url: string; type?: string; category?: string },
  usedIds: Set<string>,
): ManagedSource {
  const url = typeof entry === "string" ? entry : entry.url;
  const type = (typeof entry === "string" ? undefined : entry.type) === "pdf" ? "pdf" : inferType(url);
  const providedId = typeof entry === "string" ? undefined : entry.id;
  const id = providedId && !usedIds.has(providedId) ? (usedIds.add(providedId), providedId) : inferId(url, usedIds);

  return {
    id,
    title: (typeof entry === "string" ? undefined : entry.title) || inferTitle(url),
    url,
    type,
    category: (typeof entry === "string" ? undefined : entry.category) || inferCategory(type),
  };
}

export function extractUrls(text: string) {
  const matches = text.match(URL_REGEX) || [];
  return Array.from(new Set(matches.map(stripTrailingPunctuation)));
}

export async function loadSourcesConfig() {
  const raw = await fs.readFile(SOURCE_CONFIG_PATH, "utf-8");
  const payload = JSON.parse(raw) as SourceConfigPayload;
  const usedIds = new Set<string>();

  return {
    name: payload.name || "Web Harvest Chatbot Sources",
    sources: (payload.sources || []).map((entry) => normalizeEntry(entry, usedIds)),
  };
}

export async function saveSourcesConfig(name: string, sources: ManagedSource[]) {
  const payload = {
    name,
    sources: sources.map((source) => source.url),
  };

  await fs.writeFile(SOURCE_CONFIG_PATH, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

export async function addSourcesFromText(text: string) {
  const { name, sources } = await loadSourcesConfig();
  const existingUrls = new Set(sources.map((source) => source.url));
  const usedIds = new Set(sources.map((source) => source.id));
  const added: ManagedSource[] = [];
  const skipped: string[] = [];

  for (const url of extractUrls(text)) {
    if (existingUrls.has(url)) {
      skipped.push(url);
      continue;
    }

    const source = normalizeEntry(url, usedIds);
    sources.push(source);
    existingUrls.add(url);
    added.push(source);
  }

  await saveSourcesConfig(name, sources);
  return { name, sources, added, skipped };
}

export async function removeSourceById(id: string) {
  const { name, sources } = await loadSourcesConfig();
  const nextSources = sources.filter((source) => source.id !== id);

  if (nextSources.length === sources.length) {
    return { name, sources, removed: null };
  }

  const removed = sources.find((source) => source.id === id) || null;
  await saveSourcesConfig(name, nextSources);
  return { name, sources: nextSources, removed };
}
