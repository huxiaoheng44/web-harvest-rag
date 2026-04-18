import { NextResponse } from "next/server";

import { getAuthenticatedServerContext } from "@/lib/supabase/request-user";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";

function makeTitle(input?: string) {
  const base = (input || "New chat").trim().replace(/\s+/g, " ");
  return base.length > 60 ? `${base.slice(0, 57)}...` : base;
}

export async function GET() {
  const { user } = await getAuthenticatedServerContext();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = createSupabaseAdminClient();
  const { data, error } = await supabase
    .from("conversations")
    .select("id, title, created_at, updated_at")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ conversations: data || [] });
}

export async function POST(request: Request) {
  const { user } = await getAuthenticatedServerContext();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const title = makeTitle(body?.title);

  const supabase = createSupabaseAdminClient();
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
