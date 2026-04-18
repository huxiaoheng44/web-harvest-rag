import OpenAI from "openai";

import { getOpenAiApiKey, getOpenAiChatModel } from "@/lib/env";
import { appConfig } from "@/lib/project-config";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import type { Message, Source } from "@/lib/types";

const EMBEDDING_MODEL = "text-embedding-3-small";
const MATCH_COUNT = 6;
const MIN_SIMILARITY = 0.35;

function getOpenAiClient() {
  return new OpenAI({ apiKey: getOpenAiApiKey() });
}

type ChunkMatch = Source & {
  content: string;
  chunk_idx: number | null;
  total_chunks: number | null;
};

function buildSystemPrompt() {
  return [
    `You are ${appConfig.assistantName}, a knowledge-base assistant for a private vector database.`,
    "Answer in the same language as the user's question when possible.",
    "Use the retrieved context as the primary source of truth.",
    "If the context is insufficient, say clearly that you cannot confirm it from the current knowledge base.",
    "Do not invent facts, product details, or policies that are not supported by the provided sources.",
    "Keep answers practical and structured.",
  ].join(" ");
}

function buildContext(chunks: ChunkMatch[]) {
  return chunks
    .map((chunk, index) => {
      const title = chunk.title || "Untitled";
      const url = chunk.url || "";
      const similarity = chunk.similarity.toFixed(3);

      return [
        `[Source ${index + 1}]`,
        `Title: ${title}`,
        `URL: ${url}`,
        `Category: ${chunk.category || "unknown"}`,
        `Similarity: ${similarity}`,
        `Content: ${chunk.content}`,
      ].join("\n");
    })
    .join("\n\n");
}

export async function retrieveRelevantChunks(query: string) {
  const openai = getOpenAiClient();
  const embeddingResponse = await openai.embeddings.create({
    model: EMBEDDING_MODEL,
    input: query,
  });

  const embedding = embeddingResponse.data[0]?.embedding;
  if (!embedding) {
    throw new Error("Failed to generate query embedding.");
  }

  const supabase = createSupabaseAdminClient();
  const { data, error } = await supabase.rpc("match_chunks", {
    query_embedding: embedding,
    match_count: MATCH_COUNT,
  });

  if (error) {
    throw new Error(`Vector search failed: ${error.message}`);
  }

  return ((data || []) as ChunkMatch[]).filter(
    (chunk) => chunk.similarity >= MIN_SIMILARITY,
  );
}

export async function generateAnswer(question: string, history: Message[], chunks: ChunkMatch[]) {
  const openai = getOpenAiClient();
  const historyWithoutCurrentQuestion =
    history[history.length - 1]?.role === "user" &&
    history[history.length - 1]?.content.trim() === question.trim()
      ? history.slice(0, -1)
      : history;

  const recentHistory = historyWithoutCurrentQuestion.slice(-8).map((message) => ({
    role: message.role,
    content: message.content,
  }));

  const context = chunks.length
    ? buildContext(chunks)
    : "No relevant sources were retrieved from the knowledge base.";

  const completion = await openai.chat.completions.create({
    model: getOpenAiChatModel(),
    temperature: 0.2,
    messages: [
      { role: "system", content: buildSystemPrompt() },
      ...recentHistory,
      {
        role: "user",
        content: [
          "Answer the question using the context below.",
          "If the context is weak or empty, say that you cannot confirm from the current knowledge base.",
          "At the end, add a short 'Sources' section only when you used retrieved sources.",
          "",
          "Context:",
          context,
          "",
          `Question: ${question}`,
        ].join("\n"),
      },
    ],
  });

  return completion.choices[0]?.message?.content?.trim() || "I could not generate a response.";
}

export function mapSources(chunks: ChunkMatch[]): Source[] {
  return chunks.map(({ id, doc_id, title, url, category, similarity }) => ({
    id,
    doc_id,
    title,
    url,
    category,
    similarity,
  }));
}
