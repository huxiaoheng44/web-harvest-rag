import { NextResponse } from "next/server";

import { generateAnswer, mapSources, retrieveRelevantChunks } from "@/lib/rag";
import { getAuthenticatedServerContext } from "@/lib/supabase/request-user";

function makeTitle(input: string) {
  const base = input.trim().replace(/\s+/g, " ");
  return base.length > 60 ? `${base.slice(0, 57)}...` : base;
}

export async function POST(request: Request) {
  const { supabase, user } = await getAuthenticatedServerContext();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => null);
  const question = body?.message?.trim();

  if (!question) {
    return NextResponse.json({ error: "Message is required" }, { status: 400 });
  }

  let conversationId = body?.conversationId as string | undefined;

  if (!conversationId) {
    const { data: newConvo, error: createError } = await supabase
      .from("conversations")
      .insert({ user_id: user.id, title: makeTitle(question) })
      .select("id")
      .single();

    if (createError || !newConvo) {
      return NextResponse.json(
        { error: createError?.message || "Failed to create conversation" },
        { status: 500 },
      );
    }

    conversationId = newConvo.id;
  }

  const { data: conversation } = await supabase
    .from("conversations")
    .select("id")
    .eq("id", conversationId)
    .eq("user_id", user.id)
    .single();

  if (!conversation) {
    return NextResponse.json({ error: "Conversation not found" }, { status: 404 });
  }

  const { error: userInsertError } = await supabase.from("messages").insert({
    conversation_id: conversationId,
    role: "user",
    content: question,
  });

  if (userInsertError) {
    return NextResponse.json({ error: userInsertError.message }, { status: 500 });
  }

  const { data: history, error: historyError } = await supabase
    .from("messages")
    .select("id, role, content, created_at, sources")
    .eq("conversation_id", conversationId)
    .order("created_at", { ascending: true });

  if (historyError) {
    return NextResponse.json({ error: historyError.message }, { status: 500 });
  }

  try {
    const chunks = await retrieveRelevantChunks(question);
    const answer = await generateAnswer(question, history || [], chunks);
    const sources = mapSources(chunks);

    const { data: assistantMessage, error: assistantError } = await supabase
      .from("messages")
      .insert({
        conversation_id: conversationId,
        role: "assistant",
        content: answer,
        sources,
      })
      .select("id, role, content, created_at, sources")
      .single();

    if (assistantError || !assistantMessage) {
      return NextResponse.json(
        { error: assistantError?.message || "Failed to store assistant response" },
        { status: 500 },
      );
    }

    await supabase
      .from("conversations")
      .update({ updated_at: new Date().toISOString() })
      .eq("id", conversationId);

    return NextResponse.json({ conversationId, message: assistantMessage });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Chat request failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
