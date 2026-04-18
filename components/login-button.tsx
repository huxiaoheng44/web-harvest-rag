"use client";

import { useState } from "react";

import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export function LoginButton() {
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);
    const supabase = createSupabaseBrowserClient();

    const { error } = await supabase.auth.signInAnonymously();

    if (error) {
      setLoading(false);
      window.alert(error.message);
      return;
    }

    window.location.href = "/chat";
  }

  return (
    <button className="primary-button" onClick={handleLogin} disabled={loading}>
      {loading ? "Starting session..." : "Start anonymous session"}
    </button>
  );
}
