"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/store";
import { api } from "@/lib/api";
import { ArrowUpRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuth((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.login({ email, password });
      setAuth(res.token, res.user);
      toast.success(`Welcome back, ${res.user.full_name || res.user.email}`);
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen grid lg:grid-cols-[1.2fr_1fr]">
      {/* Left — editorial panel */}
      <aside className="relative hidden lg:flex flex-col justify-between p-12 bg-ink text-paper overflow-hidden">
        <div className="grid-noise absolute inset-0 opacity-[0.08]" />
        <div className="relative z-10 flex items-center gap-3">
          <Logomark dark />
          <span className="font-display text-lg">LeadForge</span>
        </div>

        <div className="relative z-10 max-w-md">
          <p className="status text-paper/60 mb-6">
            <span className="status-dot bg-ember" /> Local intelligence
          </p>
          <blockquote className="display text-3xl xl:text-4xl leading-[1.1] text-balance">
            "The businesses that need a website the most are often the hardest
            ones to find. Until now."
          </blockquote>
          <p className="mt-6 text-sm text-paper/60">
            Built for agencies, freelancers, and B2B sales teams.
          </p>
        </div>

        <div className="relative z-10 text-xs font-mono text-paper/40">
          v1.0 · june 2026
        </div>
      </aside>

      {/* Right — form */}
      <section className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm animate-fade-up">
          <Link
            href="/"
            className="text-xs font-mono text-ink-mute uppercase tracking-wider hover:text-ember transition-colors"
          >
            ← Back home
          </Link>

          <h1 className="display text-display-md mt-8 mb-2">
            Sign in
          </h1>
          <p className="text-ink-mute mb-12">
            Continue your lead discovery pipeline.
          </p>

          <form onSubmit={onSubmit} className="space-y-8">
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
                placeholder="••••••••"
              />
            </div>

            <button type="submit" disabled={loading} className="btn-solid w-full">
              {loading ? "Signing in…" : "Sign in"}
              {!loading && <ArrowUpRight size={16} />}
            </button>
          </form>

          <p className="mt-10 text-sm text-ink-mute">
            No account?{" "}
            <Link href="/register" className="text-ink underline-offset-4 hover:underline">
              Create one
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