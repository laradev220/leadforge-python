"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Compass,
  Loader2,
  Lock,
  Play,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { api, type QueueStats } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { formatRelative } from "@/lib/utils";

const QUEUE_LABELS: Record<string, { label: string; description: string }> = {
  discovery: {
    label: "Discovery",
    description: "Crawls Google Maps and directories for new businesses.",
  },
  website: {
    label: "Website",
    description: "Resolves & inspects business websites.",
  },
  contact: {
    label: "Contact",
    description: "Extracts emails, phones, and contact forms.",
  },
  social: {
    label: "Social",
    description: "Surfaces LinkedIn, Instagram, and other profiles.",
  },
  verification: {
    label: "Verification",
    description: "Checks email deliverability and phone line types.",
  },
  scoring: {
    label: "Scoring",
    description: "Calculates the 5-factor lead score.",
  },
  export: {
    label: "Export",
    description: "Generates CSV/XLSX/JSON exports.",
  },
};

const QUEUE_ORDER = [
  "discovery",
  "website",
  "contact",
  "social",
  "verification",
  "scoring",
  "export",
];

export default function AdminPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Record<string, QueueStats> | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = user?.role === "ADMIN";

  async function load(silent = false) {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const res = await api.queueStats();
      setStats(res.data.stats);
      setLastSync(new Date());
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load";
      setError(msg);
      if (!silent) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (!isAdmin) return;
    load();
    const interval = setInterval(() => load(true), 15_000);
    return () => clearInterval(interval);
  }, [isAdmin]);

  // Auto-refresh ticker for "X seconds ago"
  useEffect(() => {
    if (!lastSync) return;
    const interval = setInterval(() => {
      // force re-render
      setLastSync((prev) => (prev ? new Date(prev.getTime()) : prev));
    }, 1000);
    return () => clearInterval(interval);
  }, [lastSync]);

  async function handleRetry() {
    setRetrying(true);
    try {
      const res = await api.retryFailedJobs();
      toast.success(`${res.data.retried} failed jobs re-queued`);
      await load(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  }

  // ── Forbidden ───────────────────────────────────────────────────────────
  if (!isAdmin) {
    return (
      <div className="py-24 text-center max-w-md mx-auto">
        <div className="inline-flex h-14 w-14 items-center justify-center bg-paper-mute text-ink-mute mb-6">
          <Lock size={22} />
        </div>
        <p className="display text-display-md mb-3">Admin only</p>
        <p className="text-ink-mute text-sm mb-8">
          You're signed in as <span className="font-mono">{user?.email}</span>.
          The admin panel is restricted to platform administrators.
        </p>
        <Link href="/dashboard" className="btn-outline">
          Back to overview
        </Link>
      </div>
    );
  }

  // ── Aggregates ──────────────────────────────────────────────────────────
  const aggregates = stats
    ? Object.values(stats).reduce(
        (acc, q) => ({
          waiting: acc.waiting + q.waiting,
          in_progress: acc.in_progress + q.in_progress,
          complete: acc.complete + q.complete,
          failed: acc.failed + q.failed,
        }),
        { waiting: 0, in_progress: 0, complete: 0, failed: 0 },
      )
    : null;

  const hasFailures = (aggregates?.failed ?? 0) > 0;
  const isHealthy = !hasFailures && (aggregates?.in_progress ?? 0) > 0;

  return (
    <div className="space-y-12 animate-fade-up">
      <header className="space-y-4">
        <p className="status text-ink-mute">
          <span className="status-dot bg-ember animate-pulse-soft" /> system
          health · auto-refresh every 15s
        </p>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="display text-display-lg text-balance max-w-[24ch]">
            The workers behind the curtain.
          </h1>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-ink-mute uppercase tracking-wider">
              {lastSync ? `synced ${formatRelative(lastSync.toISOString())}` : "—"}
            </span>
            <button
              type="button"
              onClick={() => load(false)}
              disabled={loading || refreshing}
              className="btn-outline"
            >
              {refreshing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Aggregate KPIs */}
      <section className="grid grid-cols-2 lg:grid-cols-4 border-t border-line divide-x divide-line">
        <KpiCard
          label="Waiting"
          value={aggregates?.waiting ?? 0}
          tone="ink"
          loading={loading}
          icon={<Clock size={14} />}
        />
        <KpiCard
          label="In progress"
          value={aggregates?.in_progress ?? 0}
          tone="ember"
          loading={loading}
          icon={<Activity size={14} />}
        />
        <KpiCard
          label="Completed"
          value={aggregates?.complete ?? 0}
          tone="moss"
          loading={loading}
          icon={<CheckCircle2 size={14} />}
        />
        <KpiCard
          label="Failed"
          value={aggregates?.failed ?? 0}
          tone={hasFailures ? "ember" : "ink"}
          loading={loading}
          icon={<AlertTriangle size={14} />}
        />
      </section>

      {/* System status banner */}
      {error ? (
        <div className="border border-ember bg-ember/5 p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldAlert size={18} className="text-ember shrink-0" />
            <div>
              <p className="font-medium text-sm">Couldn't reach the queue service</p>
              <p className="text-xs text-ink-mute font-mono mt-0.5">{error}</p>
            </div>
          </div>
          <button onClick={() => load(false)} className="btn-outline">
            Retry
          </button>
        </div>
      ) : isHealthy ? (
        <div className="border border-moss/40 bg-moss/5 p-5 flex items-center gap-3">
          <CheckCircle2 size={18} className="text-moss shrink-0" />
          <p className="text-sm">
            <span className="font-medium">All systems normal.</span>{" "}
            <span className="text-ink-mute">
              {aggregates?.in_progress} jobs running across {stats ? Object.keys(stats).length : 0} queues.
            </span>
          </p>
        </div>
      ) : hasFailures ? (
        <div className="border border-ember bg-ember/5 p-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <AlertTriangle size={18} className="text-ember shrink-0" />
            <div className="min-w-0">
              <p className="font-medium text-sm">
                {aggregates?.failed} failed job{aggregates?.failed === 1 ? "" : "s"} across queues
              </p>
              <p className="text-xs text-ink-mute">
                Re-queue them to attempt another run.
              </p>
            </div>
          </div>
          <button
            onClick={handleRetry}
            disabled={retrying}
            className="btn-solid"
          >
            {retrying ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            Re-queue all
          </button>
        </div>
      ) : null}

      {/* Queue detail table */}
      <section className="border-t border-line pt-8">
        <div className="flex items-end justify-between mb-6">
          <h2 className="display text-display-md">Queues</h2>
          <span className="text-xs font-mono text-ink-mute uppercase tracking-wider">
            arq · redis
          </span>
        </div>

        {loading && !stats ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 size={20} className="animate-spin text-ink-mute" />
          </div>
        ) : stats ? (
          <div className="border-y border-line divide-y divide-line">
            {QUEUE_ORDER.map((name) => {
              const q = stats[name];
              if (!q) return null;
              const meta = QUEUE_LABELS[name] ?? {
                label: name,
                description: "",
              };
              const total = q.waiting + q.in_progress + q.complete + q.failed;
              const utilization =
                total === 0 ? 0 : ((q.in_progress + q.waiting) / total) * 100;
              return (
                <article
                  key={name}
                  className="grid grid-cols-12 gap-4 items-center py-6 px-2"
                >
                  <div className="col-span-12 md:col-span-4">
                    <p className="font-display text-lg leading-tight">
                      {meta.label}
                    </p>
                    <p className="text-xs text-ink-mute mt-1 max-w-xs">
                      {meta.description}
                    </p>
                  </div>

                  <div className="col-span-6 md:col-span-2">
                    <QueueMeter
                      waiting={q.waiting}
                      inProgress={q.in_progress}
                      failed={q.failed}
                    />
                    <p className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost mt-2">
                      load · {utilization.toFixed(0)}%
                    </p>
                  </div>

                  <div className="col-span-3 md:col-span-1 text-right">
                    <p className="display text-2xl">{q.waiting}</p>
                    <p className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
                      wait
                    </p>
                  </div>

                  <div className="col-span-3 md:col-span-1 text-right">
                    <p className="display text-2xl text-ember">
                      {q.in_progress}
                    </p>
                    <p className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
                      active
                    </p>
                  </div>

                  <div className="col-span-6 md:col-span-2 text-right">
                    <p className="font-mono text-sm text-moss">
                      {q.complete.toLocaleString()}
                    </p>
                    <p className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
                      completed
                    </p>
                  </div>

                  <div className="col-span-6 md:col-span-2 text-right">
                    <p
                      className={`font-mono text-sm ${
                        q.failed > 0 ? "text-ember" : "text-ink-ghost"
                      }`}
                    >
                      {q.failed}
                    </p>
                    <p className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
                      failed
                    </p>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </section>

      <section className="border-t border-line pt-6 flex items-center gap-3 text-sm text-ink-mute">
        <Compass size={16} className="text-ember" />
        <span>
          Need more? The export queue is rate-limited per worker.{" "}
          <Link
            href="/dashboard/exports"
            className="text-ink hover:text-ember inline-flex items-center gap-1"
          >
            Check export status <ArrowUpRight size={12} />
          </Link>
        </span>
      </section>
    </div>
  );
}

// ── Building blocks ────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  tone,
  loading,
  icon,
}: {
  label: string;
  value: number;
  tone: "ink" | "ember" | "moss";
  loading: boolean;
  icon: React.ReactNode;
}) {
  const toneClass =
    tone === "ember"
      ? "text-ember"
      : tone === "moss"
        ? "text-moss"
        : "text-ink";
  return (
    <div className="py-6 lg:py-8 lg:px-0 px-0 border-b border-line lg:border-b-0">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        <span className={toneClass}>{icon}</span>
        {label}
      </div>
      <div className={`display text-5xl ${toneClass}`}>
        {loading ? "—" : value.toLocaleString()}
      </div>
    </div>
  );
}

function QueueMeter({
  waiting,
  inProgress,
  failed,
}: {
  waiting: number;
  inProgress: number;
  failed: number;
}) {
  const total = waiting + inProgress + failed;
  if (total === 0) {
    return (
      <div className="h-1.5 bg-paper-mute relative overflow-hidden">
        <div className="absolute inset-0 bg-ink-ghost/20" />
      </div>
    );
  }
  const waitPct = (waiting / total) * 100;
  const activePct = (inProgress / total) * 100;
  const failPct = (failed / total) * 100;
  return (
    <div className="h-1.5 bg-paper-mute flex relative overflow-hidden">
      <div className="bg-ink-mute h-full" style={{ width: `${waitPct}%` }} />
      <div
        className="bg-ember h-full"
        style={{ width: `${activePct}%` }}
      />
      <div
        className="bg-red-700 h-full"
        style={{ width: `${failPct}%` }}
      />
    </div>
  );
}
