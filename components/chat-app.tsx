"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { EnvSettingsModal } from "@/components/env-settings-modal";
import { appConfig } from "@/lib/project-config";
import type { BuildStatus, Conversation, ManagedSource, Message, Source } from "@/lib/types";

type PendingMessage = Message & { pending?: boolean };

type SourcesResponse = {
  name: string;
  sources: ManagedSource[];
  buildStatus: BuildStatus;
};

const DEFAULT_BUILD_STATUS: BuildStatus = {
  state: "idle",
  summary: "No build has run yet.",
  startedAt: null,
  finishedAt: null,
  logPath: null,
};

export function ChatApp() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<PendingMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [sources, setSources] = useState<ManagedSource[]>([]);
  const [sourceBusy, setSourceBusy] = useState(false);
  const [sourceMessage, setSourceMessage] = useState<string | null>(null);
  const [buildStatus, setBuildStatus] = useState<BuildStatus>(DEFAULT_BUILD_STATUS);
  const [removingSourceId, setRemovingSourceId] = useState<string | null>(null);
  const [buildStatusExpanded, setBuildStatusExpanded] = useState(false);
  const [envModalOpen, setEnvModalOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeConversation = conversations.find((item) => item.id === activeConversationId) || null;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function fetchConversations() {
    const response = await fetch("/api/conversations", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load conversations");
    }

    const list = payload.conversations as Conversation[];
    setConversations(list);
    if (!activeConversationId && list[0]) {
      setActiveConversationId(list[0].id);
    }
  }

  async function fetchMessages(conversationId: string) {
    const response = await fetch(`/api/conversations/${conversationId}/messages`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load messages");
    }

    setMessages(payload.messages as PendingMessage[]);
  }

  async function fetchSources() {
    const response = await fetch("/api/sources", { cache: "no-store" });
    const payload = (await response.json()) as SourcesResponse & { error?: string };
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load sources");
    }

    setSources(payload.sources);
    setBuildStatus(payload.buildStatus || DEFAULT_BUILD_STATUS);
  }

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        await Promise.all([fetchConversations(), fetchSources()]);
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load data");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    void fetch("/api/env", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) {
          return;
        }
        if (Array.isArray(payload.missingRequired) && payload.missingRequired.length > 0) {
          setEnvModalOpen(true);
        }
      })
      .catch(() => {
        return;
      });
  }, []);

  useEffect(() => {
    if (buildStatus.state !== "running") {
      return;
    }

    setBuildStatusExpanded(true);

    const timer = window.setInterval(() => {
      void fetchSources().catch(() => {
        return;
      });
    }, 3000);

    return () => window.clearInterval(timer);
  }, [buildStatus.state]);

  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      return;
    }

    void fetchMessages(activeConversationId).catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to load messages");
    });
  }, [activeConversationId]);

  async function createConversation() {
    const response = await fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New chat" }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to create conversation");
    }

    const conversation = payload.conversation as Conversation;
    setConversations((current) => [conversation, ...current]);
    setActiveConversationId(conversation.id);
    setMessages([]);
  }

  async function deleteConversation(conversationId: string) {
    const response = await fetch(`/api/conversations/${conversationId}`, { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to delete conversation");
    }

    setConversations((current) => {
      const remaining = current.filter((item) => item.id !== conversationId);
      if (activeConversationId === conversationId) {
        setActiveConversationId(remaining[0]?.id || null);
        setMessages([]);
      }
      return remaining;
    });
  }

  async function submitSources(runIngestion: boolean) {
    if (!sourceText.trim()) {
      setSourceMessage("Paste one or more URLs first");
      return;
    }

    setSourceBusy(true);
    setSourceMessage(null);

    try {
      const response = await fetch("/api/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: sourceText, runIngestion }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Failed to save sources");
      }

      setSourceMessage(payload.message || "Sources updated");
      setBuildStatus(payload.buildStatus || DEFAULT_BUILD_STATUS);
      setSourceText("");
      await fetchSources();
      if (runIngestion) {
        setSourceModalOpen(false);
        setSourceMessage(null);
      }
    } catch (err) {
      setSourceMessage(err instanceof Error ? err.message : "Failed to save sources");
    } finally {
      setSourceBusy(false);
    }
  }

  async function removeSource(sourceId: string) {
    setRemovingSourceId(sourceId);
    setSourceMessage(null);

    try {
      const response = await fetch("/api/sources", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: sourceId }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Failed to remove source");
      }

      setSourceMessage(payload.message || "Source removed");
      setBuildStatus(payload.buildStatus || DEFAULT_BUILD_STATUS);
      await fetchSources();
    } catch (err) {
      setSourceMessage(err instanceof Error ? err.message : "Failed to remove source");
    } finally {
      setRemovingSourceId(null);
    }
  }

  async function sendMessage() {
    const question = input.trim();
    if (!question || sending) {
      return;
    }

    setError(null);
    setSending(true);
    setInput("");

    const optimistic: PendingMessage = {
      id: `temp-user-${Date.now()}`,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
      sources: null,
      pending: true,
    };
    setMessages((current) => [...current, optimistic]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversationId: activeConversationId, message: question }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Failed to send message");
      }

      setMessages((current) => {
        const withoutOptimistic = current.filter((message) => message.id !== optimistic.id);
        return [
          ...withoutOptimistic,
          { ...optimistic, id: `${payload.conversationId}-user-${Date.now()}`, pending: false },
          payload.message as PendingMessage,
        ];
      });
      setActiveConversationId(payload.conversationId as string);
      await fetchConversations();
    } catch (err) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      setInput(question);
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return <main className="loading-state">Loading conversations...</main>;
  }

  return (
    <>
      <main className="chat-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="brand-icon">{appConfig.brandMark}</div>
            <span className="brand-name">{appConfig.appName}</span>
            <button className="brand-settings-btn" onClick={() => setEnvModalOpen(true)} title="Environment settings">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01A1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </div>

          <button className="new-chat-btn" onClick={() => void createConversation()}>
            New chat
          </button>

          <button className="secondary-sidebar-btn" onClick={() => setSourceModalOpen(true)}>
            Add sources
          </button>

          <div className="source-status-card">
            <button
              className="source-status-toggle"
              onClick={() => setBuildStatusExpanded((current) => !current)}
            >
              <div className="source-status-top">
                <strong>Build status</strong>
                <span className={`status-pill ${buildStatus.state}`}>{buildStatus.state}</span>
              </div>
            </button>
            {buildStatusExpanded || buildStatus.state === "running" ? (
              <>
                <p>{buildStatus.summary}</p>
                <div className="source-status-meta">
                  <span>{sources.length} sources</span>
                  {buildStatus.startedAt ? <span>Started: {new Date(buildStatus.startedAt).toLocaleTimeString()}</span> : null}
                  {buildStatus.finishedAt ? <span>Finished: {new Date(buildStatus.finishedAt).toLocaleTimeString()}</span> : null}
                </div>
              </>
            ) : null}
          </div>

          <span className="sidebar-section-label">Current sources</span>
          <div className="source-mini-list">
            {sources.length === 0 ? (
              <p className="empty-copy">No sources yet. Add a few URLs to build the knowledge base.</p>
            ) : (
              sources.map((source) => (
                <div key={source.id} className="source-mini-item">
                  <div className="source-mini-copy">
                    <strong title={source.title}>{source.title}</strong>
                    <small>{source.type.toUpperCase()}</small>
                  </div>
                  <button
                    className="source-delete-btn"
                    onClick={() => void removeSource(source.id)}
                    disabled={removingSourceId === source.id}
                    title="Remove source"
                  >
                    {removingSourceId === source.id ? "..." : "x"}
                  </button>
                </div>
              ))
            )}
          </div>

          <span className="sidebar-section-label">Recent</span>
          <div className="conversation-list">
            {conversations.length === 0 ? (
              <p className="empty-copy">No chats yet.</p>
            ) : (
              conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  className={`conversation-item ${conversation.id === activeConversationId ? "active" : ""}`}
                  onClick={() => setActiveConversationId(conversation.id)}
                >
                  <span>{conversation.title}</span>
                  <span
                    className="delete-mark"
                    onClick={(event) => {
                      event.stopPropagation();
                      void deleteConversation(conversation.id);
                    }}
                  >
                    x
                  </span>
                </button>
              ))
            )}
          </div>

          <div className="sidebar-footer">
            <div className="avatar">{appConfig.brandMark}</div>
            <div>
              <strong>Anonymous session</strong>
              <p>{appConfig.knowledgeBaseLabel}</p>
            </div>
          </div>
        </aside>

        <section className="chat-panel">
          <header className="chat-header">
            <div className="chat-header-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <div className="chat-header-text">
              <h1>{activeConversation?.title || "New chat"}</h1>
              <p>{appConfig.appName} - answers grounded in indexed sources</p>
            </div>
          </header>

          <div className="message-list">
            {messages.length === 0 ? (
              <div className="empty-chat-state">
                <div className="empty-chat-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1991e6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                </div>
                <h3>{appConfig.emptyStateTitle}</h3>
                <p>{appConfig.emptyStateDescription}</p>
              </div>
            ) : (
              messages.map((message) => (
                <article key={message.id} className={`message-card ${message.role}`}>
                  <div className="message-role">{message.role === "assistant" ? appConfig.assistantName : "You"}</div>
                  <div className="message-bubble">
                    <div className="markdown-body">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  </div>
                  {message.role === "assistant" && message.sources && message.sources.length > 0 ? <SourceList sources={message.sources} /> : null}
                </article>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="composer-shell">
            {error ? <p className="error-banner">{error}</p> : null}
            <div className="composer">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void sendMessage();
                  }
                }}
                placeholder={appConfig.chatInputPlaceholder}
                rows={2}
              />
              <button className="primary-button" onClick={() => void sendMessage()} disabled={sending || !input.trim()}>
                {sending ? "Thinking..." : "Send"}
              </button>
            </div>
          </div>
        </section>
      </main>

      {sourceModalOpen ? (
        <div className="modal-overlay" onClick={() => setSourceModalOpen(false)}>
          <div className="modal-card source-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-logo">
              <div className="modal-logo-dot">{appConfig.brandMark}</div>
              <div className="modal-logo-text">Add sources</div>
            </div>

            <h2>Paste raw text with URLs</h2>
            <p>
              Paste notes, emails, copied lists, or plain URLs. The backend extracts all links, deduplicates them, and classifies each one as a web page or PDF.
            </p>

            <textarea
              className="source-textarea"
              value={sourceText}
              onChange={(event) => setSourceText(event.target.value)}
              placeholder={"https://example.com\nhttps://example.com/file.pdf\nOr paste a paragraph containing multiple URLs."}
              rows={10}
            />

            {sourceMessage ? <p className="source-feedback">{sourceMessage}</p> : null}

            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setSourceModalOpen(false)} disabled={sourceBusy}>
                Close
              </button>
              <button className="ghost-button" onClick={() => void submitSources(false)} disabled={sourceBusy}>
                {sourceBusy ? "Working..." : "Save only"}
              </button>
              <button className="primary-button" onClick={() => void submitSources(true)} disabled={sourceBusy}>
                {sourceBusy ? "Building..." : "Save and build"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <EnvSettingsModal
        isOpen={envModalOpen}
        title="Environment variables"
        description="Update the local OpenAI and Supabase variables used by the app."
        onClose={() => setEnvModalOpen(false)}
      />
    </>
  );
}

function SourceList({ sources }: { sources: Source[] }) {
  return (
    <div className="source-list">
      <p className="source-heading">Sources</p>
      {sources.map((source) => (
        <a key={source.id} className="source-card" href={source.url || "#"} target="_blank" rel="noreferrer">
          <strong>{source.title || source.doc_id}</strong>
          <span>{source.url || source.doc_id}</span>
        </a>
      ))}
    </div>
  );
}
