"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/store";
import { useTheme } from "@/lib/theme";
import { LogOut, Compass, Moon, Sun, Menu, X } from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/jobs", label: "Search jobs" },
  { href: "/dashboard/leads", label: "Leads" },
  { href: "/dashboard/businesses", label: "Businesses" },
  { href: "/dashboard/socials", label: "Socials" },
  { href: "/dashboard/exports", label: "Exports" },
  { href: "/dashboard/analytics", label: "Analytics" },
  { href: "/dashboard/settings", label: "Settings" },
  { href: "/dashboard/admin", label: "Admin", admin: true },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { token, user, clear } = useAuth();
  const { theme, toggle } = useTheme();
  const [hydrated, setHydrated] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile nav on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Wait for zustand to rehydrate from localStorage before deciding to redirect
  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      router.replace("/login");
    }
  }, [hydrated, token, router]);

  if (!hydrated || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="font-mono text-xs uppercase tracking-wider text-ink-mute animate-pulse-soft">
          Loading…
        </div>
      </div>
    );
  }

  function onLogout() {
    clear();
    router.push("/login");
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      {/* Mobile header */}
      <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-line sticky top-0 z-30 bg-paper/95 backdrop-blur">
        <Link href="/" className="flex items-center gap-2">
          <Logomark />
          <span className="font-display text-base">LeadForge</span>
        </Link>
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="p-2 -mr-2"
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
      </header>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-ink/40 z-40 animate-fade-in"
          onClick={() => setMobileOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar — drawer on mobile, fixed on desktop */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-[280px] border-r border-line bg-paper-deep flex flex-col transition-transform duration-300 ease-out lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="px-6 py-6 border-b border-line flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <Logomark />
            <span className="font-display text-lg">LeadForge</span>
          </Link>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1 -mr-1"
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
          {NAV.filter((item) => !item.admin || user?.role === "ADMIN").map((item) => {
            const active =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-4 py-2.5 text-sm transition-colors ${
                  active
                    ? "bg-ink text-paper"
                    : "text-ink-soft hover:bg-paper-mute hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-line p-4 space-y-3">
          <button
            onClick={toggle}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs font-mono uppercase tracking-wider text-ink-mute hover:text-ink transition-colors"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <div className="flex items-center gap-3 px-2">
            <div className="h-8 w-8 rounded-full bg-ember/20 text-ember flex items-center justify-center font-display text-sm">
              {(user?.full_name || user?.email || "?").charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">
                {user?.full_name || user?.email}
              </div>
              <div className="text-xs text-ink-mute truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs font-mono uppercase tracking-wider text-ink-mute hover:text-ember transition-colors"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="relative overflow-x-hidden">
        <div className="px-4 md:px-8 lg:px-12 py-6 lg:py-8 max-w-[1400px] mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}

function Logomark() {
  return (
    <svg width="24" height="24" viewBox="0 0 28 28" fill="none" aria-hidden>
      <path
        d="M4 24V4h2v18h6v2H4zm10 0V8h2v14h6v2h-8zm10 0V14h2v8h-2z"
        fill="currentColor"
      />
      <circle cx="14" cy="14" r="3" className="fill-ember" />
    </svg>
  );
}