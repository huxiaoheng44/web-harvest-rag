import { redirect } from "next/navigation";

import { LoginButton } from "@/components/login-button";
import { appConfig } from "@/lib/project-config";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export default async function LoginPage() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    redirect("/chat");
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <p className="eyebrow">{appConfig.appName}</p>
        <h1>Chat with your indexed website and PDF corpus</h1>
        <p className="login-copy">
          Start an anonymous session, search your indexed content, and keep conversation history
          in Supabase for follow-up questions.
        </p>
        <LoginButton />
      </section>
    </main>
  );
}
