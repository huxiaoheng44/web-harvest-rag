import { NextResponse } from "next/server";

import { getAuthenticatedServerContext } from "@/lib/supabase/request-user";

function makeTitle(input?: string) {
  const base = (input || "New chat").trim().replace(/\s+/g, " ");
  return base.length > 60 ? `${base.slice(0, 57)}...` : base;
}

export async function GET() {
  const { supabase, user } = await getAuthenticatedServerContext();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("conversations")
    .select("id, title, created_at, updated_at")
    .order("updated_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ conversations: data || [] });
}

export async function POST(request: Request) {
  const { supabase, user } = await getAuthenticatedServerContext();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const title = makeTitle(body?.title);

  const { data, error } = await supabase
    .from("conversations")
    .insert({ user_id: user.id, title })
    .select("id, title, created_at, updated_at")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ conversation: data });
}
