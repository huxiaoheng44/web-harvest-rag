"use client";

import { useState } from "react";

import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export function LoginButton() {
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);

    const configResponse = await fetch("/api/env", { cache: "no-store" });
    const configPayload = await configResponse.json();
    if (!configResponse.ok) {
      setLoading(false);
      window.alert(configPayload.error || "Failed to load environment variables");
      return;
    }

    const url = configPayload.entries?.find((entry: { key: string; value: string }) => entry.key === "NEXT_PUBLIC_SUPABASE_URL")?.value;
    const anonKey = configPayload.entries?.find((entry: { key: string; value: string }) => entry.key === "NEXT_PUBLIC_SUPABASE_ANON_KEY")?.value;

    if (!url || !anonKey) {
      setLoading(false);
      window.alert("Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY first.");
      return;
    }

    const supabase = createSupabaseBrowserClient({ url, anonKey });

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
