"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/store";
import { api } from "@/lib/api";
import { ArrowUpRight } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuth((s) => s.setAuth);
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
  });
  const [loading, setLoading] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.register(form);
      setAuth(res.token, res.user);
      toast.success("Account created");
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen grid lg:grid-cols-[1.2fr_1fr]">
      <aside className="relative hidden lg:flex flex-col justify-between p-12 bg-ink text-paper overflow-hidden">
        <div className="grid-noise absolute inset-0 opacity-[0.08]" />
        <div className="relative z-10 flex items-center gap-3">
          <Logomark dark />
          <span className="font-display text-lg">LeadForge</span>
        </div>

        <div className="relative z-10 max-w-md">
          <p className="status text-paper/60 mb-6">
            <span className="status-dot bg-ember" /> Get started
          </p>
          <h2 className="display text-4xl xl:text-5xl leading-[1.05] text-balance">
            Four steps from idea to qualified leads.
          </h2>

          <ol className="mt-10 space-y-5 text-sm text-paper/80">
            {[
              "Create an account in 30 seconds",
              "Search by keyword + location",
              "Workers enrich every result",
              "Export ranked leads on demand",
            ].map((text, i) => (
              <li key={i} className="flex gap-4 items-start">
                <span className="font-mono text-xs text-ember mt-0.5">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>{text}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="relative z-10 text-xs font-mono text-paper/40">
          free during beta
        </div>
      </aside>

      <section className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm animate-fade-up">
          <Link
            href="/"
            className="text-xs font-mono text-ink-mute uppercase tracking-wider hover:text-ember transition-colors"
          >
            ← Back home
          </Link>

          <h1 className="display text-display-md mt-8 mb-2">
            Create account
          </h1>
          <p className="text-ink-mute mb-12">
            Start discovering local businesses.
          </p>

          <form onSubmit={onSubmit} className="space-y-8">
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Full name
              </label>
              <input
                type="text"
                autoComplete="name"
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                className="field"
                placeholder="Jane Cooper"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Email
              </label>
              <input
                type="email"
                autoComplete="email"
                required
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                className="field"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Password
              </label>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                className="field"
                placeholder="min. 8 characters"
              />
            </div>

            <button type="submit" disabled={loading} className="btn-solid w-full">
              {loading ? "Creating…" : "Create account"}
              {!loading && <ArrowUpRight size={16} />}
            </button>
          </form>

          <p className="mt-10 text-sm text-ink-mute">
            Already have one?{" "}
            <Link href="/login" className="text-ink underline-offset-4 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}

function Logomark({ dark = false }: { dark?: boolean }) {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <path
        d="M4 24V4h2v18h6v2H4zm10 0V8h2v14h6v2h-8zm10 0V14h2v8h-2z"
        fill={dark ? "oklch(0.97 0.012 80)" : "currentColor"}
      />
      <circle cx="14" cy="14" r="3" fill="oklch(0.58 0.18 38)" />
    </svg>
  );
}