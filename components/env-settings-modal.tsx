"use client";

import { useEffect, useMemo, useState } from "react";

import type { EnvEntry, EnvField } from "@/lib/types";

type EnvResponse = {
  entries: EnvEntry[];
  fixedFields: EnvField[];
  missingRequired: string[];
  message?: string;
};

type Props = {
  isOpen: boolean;
  allowLater?: boolean;
  title: string;
  description: string;
  onClose: () => void;
  onSaved?: () => void;
};

// "__ALL__" is a sentinel meaning the full-form Save triggered the confirmation
const SAVE_ALL_KEY = "__ALL__";

function isSensitiveKey(key: string, sensitiveFixedKeys: Set<string>) {
  if (sensitiveFixedKeys.has(key)) return true;
  return /KEY|TOKEN|SECRET|PASSWORD/i.test(key);
}

export function EnvSettingsModal({ isOpen, allowLater = false, title, description, onClose, onSaved }: Props) {
  const [entries, setEntries] = useState<EnvEntry[]>([]);
  const [fixedFields, setFixedFields] = useState<EnvField[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  // pendingKey: which key (or SAVE_ALL_KEY) is waiting for sensitive confirmation
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const sensitiveFixedKeys = useMemo(() => new Set(fixedFields.filter((f) => f.sensitive).map((f) => f.key)), [fixedFields]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setLoading(true);
    setMessage(null);

    void fetch("/api/env", { cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as EnvResponse & { error?: string };
        if (!response.ok) {
          throw new Error(payload.error || "Failed to load environment settings");
        }
        setEntries(payload.entries);
        setFixedFields(payload.fixedFields);
      })
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Failed to load environment settings");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [isOpen]);

  function updateEntry(key: string, value: string) {
    setEntries((current) => current.map((entry) => (entry.key === key ? { ...entry, value } : entry)));
  }

  function toggleVisibility(key: string) {
    setVisibleKeys((current) => ({ ...current, [key]: !current[key] }));
  }

  async function persist(key: string, allEntries: EnvEntry[]) {
    setSavingKey(key);
    setMessage(null);

    try {
      const response = await fetch("/api/env", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries: allEntries }),
      });
      const payload = (await response.json()) as EnvResponse & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Failed to save environment settings");
      }

      setEntries(payload.entries);
      setFixedFields(payload.fixedFields);
      setSavedKey(key);
      setTimeout(() => setSavedKey((current) => (current === key ? null : current)), 2000);
      localStorage.setItem("whc-env-onboarding-seen", "true");
      onSaved?.();

      // Close after full-form save
      if (key === SAVE_ALL_KEY) {
        onClose();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save environment settings");
    } finally {
      setSavingKey(null);
    }
  }

  // Apply a single field — only checks sensitivity of that field
  async function applyEntry(key: string, skipConfirm = false) {
    const entry = entries.find((e) => e.key === key);
    const hasValue = Boolean(entry?.value.trim());

    if (!skipConfirm && hasValue && isSensitiveKey(key, sensitiveFixedKeys)) {
      setPendingKey(key);
      return;
    }

    await persist(key, entries);
  }

  // Save all — checks if any sensitive field has a value
  async function saveAll(skipConfirm = false) {
    const hasSensitive = entries.some(
      (entry) => entry.value.trim() && isSensitiveKey(entry.key, sensitiveFixedKeys),
    );

    if (!skipConfirm && hasSensitive) {
      setPendingKey(SAVE_ALL_KEY);
      return;
    }

    await persist(SAVE_ALL_KEY, entries);
  }

  // Called when user confirms the sensitive warning dialog
  function confirmPending() {
    const key = pendingKey;
    setPendingKey(null);
    if (!key) return;

    if (key === SAVE_ALL_KEY) {
      void saveAll(true);
    } else {
      void applyEntry(key, true);
    }
  }

  if (!isOpen) {
    return null;
  }

  const isSavingAll = savingKey === SAVE_ALL_KEY;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card env-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-logo">
          <div className="modal-logo-dot">W</div>
          <div className="modal-logo-text">Environment settings</div>
        </div>

        <h2>{title}</h2>
        <p>{description}</p>

        {loading ? <p className="env-settings-note">Loading environment variables...</p> : null}

        {!loading ? (
          <div className="env-field-list">
            {fixedFields.map((field) => {
              const entry = entries.find((item) => item.key === field.key) || { key: field.key, value: field.defaultValue || "", isCustom: false };
              const isBusy = savingKey === field.key;
              const isDone = savedKey === field.key;
              return (
                <div key={field.key} className="env-field-card">
                  <div className="env-field-header">
                    <span>{field.key}</span>
                    <span className="hint-wrap">
                      <span className="hint-icon">?</span>
                      <span className="hint-tooltip">{field.hint}</span>
                    </span>
                  </div>
                  <div className="env-input-row">
                    <div className="env-input-wrap">
                      <input
                        className="modal-input"
                        type={field.sensitive && !visibleKeys[field.key] ? "password" : "text"}
                        value={entry.value}
                        onChange={(event) => updateEntry(field.key, event.target.value)}
                        placeholder={field.defaultValue || field.label}
                      />
                      {field.sensitive ? (
                        <button className="env-eye-btn" type="button" onClick={() => toggleVisibility(field.key)} title={visibleKeys[field.key] ? "Hide" : "Show"}>
                          {visibleKeys[field.key] ? (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                              <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          )}
                        </button>
                      ) : null}
                    </div>
                    {allowLater ? (
                      <button
                        className={`ghost-button env-apply-btn${isDone ? " env-apply-btn--done" : ""}`}
                        type="button"
                        disabled={isBusy}
                        onClick={() => void applyEntry(field.key)}
                      >
                        {isBusy ? "..." : isDone ? "Saved" : "Apply"}
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}

        {message ? <p className="source-feedback">{message}</p> : null}

        <div className="modal-actions">
          {allowLater ? (
            <button
              className="ghost-button"
              onClick={() => {
                localStorage.setItem("whc-env-onboarding-seen", "true");
                onClose();
              }}
            >
              Later
            </button>
          ) : (
            <>
              <button className="ghost-button" onClick={onClose} disabled={isSavingAll}>
                Close
              </button>
              <button
                className="primary-button"
                onClick={() => void saveAll()}
                disabled={loading || isSavingAll}
              >
                {isSavingAll ? "Saving..." : "Save settings"}
              </button>
            </>
          )}
        </div>

        {pendingKey ? (
          <div className="modal-overlay env-confirm-overlay" onClick={() => setPendingKey(null)}>
            <div className="modal-card env-confirm-card" onClick={(event) => event.stopPropagation()}>
              <h2>Sensitive values detected</h2>
              <p className="env-danger-note">
                This UI-based env editor is only intended for local development testing. If you deploy this app to the internet, do not save API keys, tokens, or service-role secrets through the frontend.
              </p>
              <p>
                For production or shared environments, put these values directly in the backend <code>.env</code> file or in your deployment platform secret manager.
              </p>
              <div className="modal-actions">
                <button className="ghost-button" onClick={() => setPendingKey(null)}>
                  Cancel
                </button>
                <button className="primary-button" onClick={confirmPending}>
                  Save for local testing
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
