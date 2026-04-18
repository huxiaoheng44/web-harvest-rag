import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function getAuthenticatedServerContext() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error) {
    throw new Error(error.message);
  }

  return { supabase, user };
}
