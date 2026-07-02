import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Top bar */}
      <header className="relative z-10 flex items-center justify-between px-6 md:px-12 py-6 animate-fade-in">
        <div className="flex items-center gap-3">
          <Logomark />
          <span className="font-display text-lg tracking-tight">LeadForge</span>
        </div>
        <nav className="hidden md:flex items-center gap-8 text-sm text-ink-soft">
          <Link href="#features" className="btn-ghost">Features</Link>
          <Link href="#pipeline" className="btn-ghost">Pipeline</Link>
          <Link href="/login" className="btn-ghost">Sign in</Link>
        </nav>
        <Link
          href="/register"
          className="btn-solid hidden md:inline-flex"
        >
          Get started <ArrowUpRight size={16} />
        </Link>
      </header>

      {/* Hero */}
      <section className="relative z-10 px-6 md:px-12 pt-20 md:pt-32 pb-24 max-w-[1400px] mx-auto">
        <div className="grid-noise absolute inset-0 -z-10 opacity-40" />

        <div className="flex items-center gap-3 mb-8 animate-fade-up" style={{ animationDelay: "0.1s" }}>
          <span className="status-dot bg-ember animate-pulse-soft" />
          <span className="status text-ink-mute">
            v1.0 · queue-driven enrichment
          </span>
        </div>

        <h1
          className="display text-display-xl text-balance max-w-[14ch] animate-fade-up"
          style={{ animationDelay: "0.2s" }}
        >
          Find businesses worth{" "}
          <em className="not-italic text-ember">talking to.</em>
        </h1>

        <p
          className="mt-8 max-w-xl text-lg md:text-xl text-ink-soft leading-relaxed text-balance animate-fade-up"
          style={{ animationDelay: "0.35s" }}
        >
          LeadForge crawls Google Maps, business directories, and the open web
          to surface local businesses — then enriches, scores, and ranks them
          by outreach potential.
        </p>

        <div
          className="mt-12 flex flex-wrap items-center gap-4 animate-fade-up"
          style={{ animationDelay: "0.5s" }}
        >
          <Link href="/register" className="btn-solid">
            Start discovering <ArrowUpRight size={16} />
          </Link>
          <Link href="/login" className="btn-ghost text-base">
            I have an account
          </Link>
        </div>

        {/* Editorial meta strip */}
        <div
          className="mt-24 grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-6 border-t border-line pt-8 animate-fade-up"
          style={{ animationDelay: "0.7s" }}
        >
          {[
            ["01", "Discovery", "Google Maps + 40+ directories"],
            ["02", "Enrichment", "Sites, contacts, socials"],
            ["03", "Scoring", "A+ through F grading"],
            ["04", "Export", "CSV, JSON, XLSX"],
          ].map(([num, label, desc]) => (
            <div key={num} className="space-y-1">
              <div className="font-mono text-xs text-ink-ghost">{num}</div>
              <div className="font-display text-xl">{label}</div>
              <div className="text-sm text-ink-mute">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-line mt-12 px-6 md:px-12 py-8 flex flex-wrap items-center justify-between gap-4 text-xs text-ink-mute font-mono">
        <span>© 2026 · LeadForge</span>
        <span>Built on FastAPI · Arq · PostgreSQL</span>
      </footer>
    </main>
  );
}

function Logomark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <path
        d="M4 24V4h2v18h6v2H4zm10 0V8h2v14h6v2h-8zm10 0V14h2v8h-2z"
        fill="currentColor"
      />
      <circle cx="14" cy="14" r="3" fill="oklch(0.58 0.18 38)" />
    </svg>
  );
}