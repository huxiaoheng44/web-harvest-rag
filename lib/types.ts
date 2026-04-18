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
