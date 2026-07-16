export type EnvFieldMeta = {
  key: string;
  label: string;
  defaultValue?: string;
  hint: string;
  sensitive?: boolean;
};

export const FIXED_ENV_FIELDS: EnvFieldMeta[] = [
  {
    key: "OPENAI_API_KEY",
    label: "OpenAI API Key",
    hint: "Create this in the OpenAI dashboard under API keys. This frontend entry flow is only for local development testing. For any internet-facing deployment, set this in backend secrets instead.",
    sensitive: true,
  },
  {
    key: "OPENAI_CHAT_MODEL",
    label: "OpenAI Chat Model",
    defaultValue: "gpt-4o-mini",
    hint: "Use the model name you want for chat completions. Common options include gpt-4o-mini or a newer chat-capable model from your OpenAI account.",
  },
  {
    key: "OPENAI_EMBED_MODEL",
    label: "OpenAI Embed Model",
    defaultValue: "text-embedding-3-small",
    hint: "This should be an embedding model from OpenAI. text-embedding-3-small is a good default for this project.",
  },
  {
    key: "SUPABASE_URL",
    label: "Supabase URL",
    hint: "In Supabase, open Project Settings -> API. Copy the Project URL.",
  },
  {
    key: "SUPABASE_SERVICE_ROLE_KEY",
    label: "Supabase Service Role Key",
    hint: "In Supabase, open Project Settings -> API. Copy the service_role secret key. This is highly sensitive and should only be used here for local development testing, not public deployment.",
    sensitive: true,
  },
  {
    key: "NEXT_PUBLIC_API_BASE_URL",
    label: "FastAPI Base URL",
    defaultValue: "http://localhost:8000",
    hint: "The frontend calls this FastAPI backend URL for chat, sources, and conversation APIs.",
  },
  {
    key: "FRONTEND_ORIGIN",
    label: "Frontend Origin",
    defaultValue: "http://localhost:3000",
    hint: "Allowed browser origin for the FastAPI CORS configuration.",
  },
];

export function isValidEnvKey(key: string) {
  return /^[A-Z][A-Z0-9_]*$/.test(key);
}
