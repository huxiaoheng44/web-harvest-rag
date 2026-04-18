function getEnv(name: string, fallbacks: string[] = []) {
  const value = [name, ...fallbacks]
    .map((key) => process.env[key])
    .find((candidate) => typeof candidate === "string" && candidate.length > 0);

  if (!value) {
    throw new Error(`Missing environment variable: ${name}`);
  }

  return value;
}

export function getOpenAiApiKey() {
  return getEnv("OPENAI_API", ["OPENAI_API_KEY"]);
}

export function getOpenAiChatModel() {
  return process.env.OPENAI_CHAT_MODEL || "gpt-4o-mini";
}

export function getSupabaseUrl() {
  return getEnv("SUPABASE_URL", ["NEXT_PUBLIC_SUPABASE_URL"]);
}

export function getSupabaseAnonKey() {
  return getEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");
}

export function getSupabaseServiceRoleKey() {
  return getEnv("SUPABASE_SERVICE_ROLE_KEY", ["SUPABASE_KEY"]);
}
