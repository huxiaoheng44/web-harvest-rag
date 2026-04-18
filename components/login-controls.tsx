"use client";

import { useEffect, useState } from "react";

import { EnvSettingsModal } from "@/components/env-settings-modal";
import { LoginButton } from "@/components/login-button";

export function LoginControls() {
  const [envModalOpen, setEnvModalOpen] = useState(false);

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

  return (
    <>
      <div className="login-actions">
        <LoginButton />
        <button className="ghost-button" onClick={() => setEnvModalOpen(true)}>
          Configure environment variables
        </button>
      </div>

      <EnvSettingsModal
        isOpen={envModalOpen}
        allowLater
        title="Set up your local environment variables"
        description="Add your OpenAI and Supabase values here. You can skip for now and come back later from the app settings."
        onClose={() => setEnvModalOpen(false)}
      />
    </>
  );
}
