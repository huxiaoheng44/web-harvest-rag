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

export function EnvSettingsModal({ isOpen, allowLater = false, title, description, onClose, onSaved }: Props) {
  const [entries, setEntries] = useState<EnvEntry[]>([]);
  const [fixedFields, setFixedFields] = useState<EnvField[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [customKey, setCustomKey] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [confirmSensitiveSave, setConfirmSensitiveSave] = useState(false);

  const fixedKeys = useMemo(() => new Set(fixedFields.map((field) => field.key)), [fixedFields]);
  const customEntries = entries.filter((entry) => !fixedKeys.has(entry.key));

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

  function removeCustomEntry(key: string) {
    setEntries((current) => current.filter((entry) => entry.key !== key));
  }

  function addCustomEntry() {
    const nextKey = customKey.trim().toUpperCase();
    if (!nextKey) {
      setMessage("Custom environment variable key is required.");
      return;
    }

    if (!/^[A-Z][A-Z0-9_]*$/.test(nextKey)) {
      setMessage("Custom keys must use uppercase letters, numbers, and underscores only.");
      return;
    }

    if (entries.some((entry) => entry.key === nextKey)) {
      setMessage("That environment variable already exists.");
      return;
    }

    setEntries((current) => [...current, { key: nextKey, value: customValue, isCustom: true }]);
    setCustomKey("");
    setCustomValue("");
    setMessage(null);
  }

  function hasSensitiveValues() {
    const sensitiveFixedKeys = new Set(fixedFields.filter((field) => field.sensitive).map((field) => field.key));
    const sensitiveCustomPattern = /KEY|TOKEN|SECRET|PASSWORD/i;

    return entries.some((entry) => {
      if (!entry.value.trim()) {
        return false;
      }

      if (sensitiveFixedKeys.has(entry.key)) {
        return true;
      }

      return entry.isCustom && sensitiveCustomPattern.test(entry.key);
    });
  }

  async function saveEntries(skipConfirm = false) {
    if (!skipConfirm && hasSensitiveValues()) {
      setConfirmSensitiveSave(true);
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch("/api/env", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries }),
      });
      const payload = (await response.json()) as EnvResponse & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Failed to save environment settings");
      }

      setEntries(payload.entries);
      setFixedFields(payload.fixedFields);
      setMessage(payload.message || "Environment variables saved locally.");
      localStorage.setItem("whc-env-onboarding-seen", "true");
      onSaved?.();
      onClose();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save environment settings");
    } finally {
      setSaving(false);
    }
  }

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card env-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-logo">
          <div className="modal-logo-dot">W</div>
          <div className="modal-logo-text">Environment settings</div>
        </div>

        <h2>{title}</h2>
        <p>{description}</p>
        <p className="env-danger-note">
          Local development only: if you enter API keys, tokens, or service-role secrets here, they are being sent through the frontend UI. Do not use this flow for internet-facing production deployments.
        </p>

        {loading ? <p className="env-settings-note">Loading environment variables...</p> : null}

        {!loading ? (
          <div className="env-field-list">
            {fixedFields.map((field) => {
              const entry = entries.find((item) => item.key === field.key) || { key: field.key, value: field.defaultValue || "", isCustom: false };
              return (
                <label key={field.key} className="env-field-card">
                  <div className="env-field-header">
                    <span>{field.key}</span>
                    <span className="hint-wrap">
                      <span className="hint-icon">?</span>
                      <span className="hint-tooltip">{field.hint}</span>
                    </span>
                  </div>
                  <div className="env-input-row">
                    <input
                      className="modal-input"
                      type={field.sensitive && !visibleKeys[field.key] ? "password" : "text"}
                      value={entry.value}
                      onChange={(event) => updateEntry(field.key, event.target.value)}
                      placeholder={field.defaultValue || field.label}
                    />
                    {field.sensitive ? (
                      <button className="env-eye-btn" type="button" onClick={() => toggleVisibility(field.key)}>
                        {visibleKeys[field.key] ? "Hide" : "Show"}
                      </button>
                    ) : null}
                  </div>
                  {field.sensitive ? (
                    <p className="env-sensitive-hint">
                      Sensitive value. Use this only for local development testing. For production, configure it directly in backend secrets.
                    </p>
                  ) : null}
                </label>
              );
            })}

            <div className="env-custom-block">
              <div className="env-custom-title">Custom variables</div>
              {customEntries.length ? (
                customEntries.map((entry) => (
                  <div key={entry.key} className="env-custom-row">
                    <input
                      className="modal-input env-custom-key"
                      value={entry.key}
                      disabled
                    />
                    <div className="env-input-row">
                      <input
                        className="modal-input"
                        type={/KEY|TOKEN|SECRET|PASSWORD/i.test(entry.key) && !visibleKeys[entry.key] ? "password" : "text"}
                        value={entry.value}
                        onChange={(event) => updateEntry(entry.key, event.target.value)}
                        placeholder="Value"
                      />
                      {/KEY|TOKEN|SECRET|PASSWORD/i.test(entry.key) ? (
                        <button className="env-eye-btn" type="button" onClick={() => toggleVisibility(entry.key)}>
                          {visibleKeys[entry.key] ? "Hide" : "Show"}
                        </button>
                      ) : null}
                    </div>
                    <button className="source-delete-btn env-remove-btn" onClick={() => removeCustomEntry(entry.key)}>
                      x
                    </button>
                  </div>
                ))
              ) : (
                <p className="env-settings-note">No custom environment variables yet.</p>
              )}

              <div className="env-custom-row env-custom-add-row">
                <input
                  className="modal-input env-custom-key"
                  value={customKey}
                  onChange={(event) => setCustomKey(event.target.value.toUpperCase())}
                  placeholder="CUSTOM_KEY"
                />
                <input className="modal-input" value={customValue} onChange={(event) => setCustomValue(event.target.value)} placeholder="Value" />
                <button className="ghost-button" onClick={addCustomEntry} type="button">
                  Add
                </button>
              </div>
            </div>
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
              disabled={saving}
            >
              Later
            </button>
          ) : (
            <button className="ghost-button" onClick={onClose} disabled={saving}>
              Close
            </button>
          )}
          <button className="primary-button" onClick={() => void saveEntries()} disabled={loading || saving}>
            {saving ? "Saving..." : "Save settings"}
          </button>
        </div>

        {confirmSensitiveSave ? (
          <div className="modal-overlay env-confirm-overlay" onClick={() => setConfirmSensitiveSave(false)}>
            <div className="modal-card env-confirm-card" onClick={(event) => event.stopPropagation()}>
              <h2>Sensitive values detected</h2>
              <p className="env-danger-note">
                This UI-based env editor is only intended for local development testing. If you deploy this app to the internet, do not save API keys, tokens, or service-role secrets through the frontend.
              </p>
              <p>
                For production or shared environments, put these values directly in the backend `.env` file or in your deployment platform secret manager.
              </p>
              <div className="modal-actions">
                <button className="ghost-button" onClick={() => setConfirmSensitiveSave(false)}>
                  Cancel
                </button>
                <button
                  className="primary-button"
                  onClick={() => {
                    setConfirmSensitiveSave(false);
                    void saveEntries(true);
                  }}
                >
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
