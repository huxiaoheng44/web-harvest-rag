export type Source = {
  id: string;
  doc_id: string;
  title: string | null;
  url: string | null;
  category: string | null;
  similarity: number;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  sources?: Source[] | null;
};

export type ProfileSummary = {
  id: string;
  email: string;
  name: string;
  avatarUrl: string;
};

export type ManagedSource = {
  id: string;
  title: string;
  url: string;
  type: "html" | "pdf";
  category: string;
};

export type BuildStatus = {
  state: "idle" | "running" | "success" | "error";
  summary: string;
  startedAt: string | null;
  finishedAt: string | null;
  logPath: string | null;
};

export type EnvField = {
  key: string;
  label: string;
  defaultValue?: string;
  hint: string;
  sensitive?: boolean;
};

export type EnvEntry = {
  key: string;
  value: string;
  isCustom: boolean;
};
