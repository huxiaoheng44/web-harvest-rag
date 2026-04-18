"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { appConfig } from "@/lib/project-config";
import type { Conversation, Message, Source } from "@/lib/types";

type PendingMessage = Message & { pending?: boolean };

export function ChatApp() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<PendingMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeConversation = conversations.find((item) => item.id === activeConversationId) || null;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function fetchConversations() {
    const response = await fetch("/api/conversations", {
      cache: "no-store",
    });
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
    const response = await fetch(`/api/conversations/${conversationId}/messages`, {
      cache: "no-store",
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load messages");
    }

    setMessages(payload.messages as PendingMessage[]);
  }

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        await fetchConversations();
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
    const response = await fetch(`/api/conversations/${conversationId}`, {
      method: "DELETE",
    });
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
    <main className="chat-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">{appConfig.brandMark}</div>
          <span className="brand-name">{appConfig.appName}</span>
        </div>

        <button className="new-chat-btn" onClick={() => void createConversation()}>
          New chat
        </button>

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
                <div className="message-role">
                  {message.role === "assistant" ? appConfig.assistantName : "You"}
                </div>
                <div className="message-bubble">
                  <div className="markdown-body">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                </div>
                {message.role === "assistant" && message.sources && message.sources.length > 0 ? (
                  <SourceList sources={message.sources} />
                ) : null}
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
