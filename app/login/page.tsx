import { redirect } from "next/navigation";

import { LoginControls } from "@/components/login-controls";
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
        <h1>Turn websites and PDFs into a searchable chatbot</h1>
        <p className="login-copy">
          Start an anonymous session, add source URLs, build the knowledge base, and chat with the
          indexed content from one UI.
        </p>
        <LoginControls />
      </section>
    </main>
  );
}
