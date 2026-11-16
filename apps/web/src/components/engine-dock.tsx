"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  Download,
  Gauge,
  Globe,
  Mail,
  Search,
  Share2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import type { EngineActivity, EngineRun } from "@/lib/types";

const WORKER_ICONS: Record<string, typeof Search> = {
  discovery: Search,
  website: Globe,
  contact: Mail,
  social: Share2,
  verification: ShieldCheck,
  scoring: Gauge,
  export: Download,
};

function elapsed(startedAt: string | null, now: number): string {
  if (!startedAt) return "";
  const seconds = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function duration(ms: number | null): string {
  if (ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function EngineDock() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"active" | "recent">("active");
  const [activity, setActivity] = useState<EngineActivity | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await api.getEngineActivity(12);
        if (!cancelled) setActivity(res.data);
      } catch {
        /* engine dock is non-critical */
      }
    }
    load();
    const interval = setInterval(load, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!activity?.active.length) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [activity?.active.length]);

  const active = activity?.active ?? [];
  const recent = activity?.recent ?? [];
  const rows = useMemo(() => (tab === "active" ? active : recent), [tab, active, recent]);
  const queued = activity?.counts.waiting ?? 0;

  return (
    <div className="fixed bottom-4 right-4 z-40 font-mono text-xs">
      {open ? (
        <div className="w-[420px] max-w-[calc(100vw-2rem)] rounded-lg border border-white/10 bg-[#141210] text-[#d8d2c8] shadow-2xl">
          <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
            <Sparkles size={14} className="text-ember" />
            <span className="font-semibold uppercase tracking-[0.16em] text-[11px]">
              LeadForge Engine
            </span>
            <span className="ml-auto flex items-center gap-2 text-[10px] text-[#8d857a]">
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                {active.length} live
              </span>
              <span>{queued} queued</span>
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="ml-1 text-[#8d857a] hover:text-white"
              aria-label="Collapse engine panel"
            >
              <ChevronDown size={16} />
            </button>
          </div>

          <div className="flex flex-wrap gap-1.5 border-b border-white/10 px-3 py-2">
            {Object.entries(activity?.queues ?? {}).map(([name, count]) => (
              <Link
                key={name}
                href="/dashboard/admin"
                className={`rounded-sm border px-1.5 py-0.5 text-[10px] ${
                  count > 0
                    ? "border-ember/50 text-ember"
                    : "border-white/10 text-[#6f675d]"
                }`}
              >
                {name.slice(0, 4)} {count}
              </Link>
            ))}
          </div>

          <div className="flex gap-1 px-3 pt-3">
            {(["active", "recent"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setTab(value)}
                className={`rounded-sm px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] ${
                  tab === value
                    ? "bg-white/10 text-white"
                    : "text-[#8d857a] hover:text-white"
                }`}
              >
                {value}
                <span className="ml-1 text-[#6f675d]">
                  {value === "active" ? active.length : recent.length}
                </span>
              </button>
            ))}
          </div>

          <div className="max-h-[46vh] overflow-y-auto px-1.5 py-2">
            {rows.length === 0 ? (
              <p className="px-3 py-6 text-center text-[#6f675d]">
                {tab === "active"
                  ? "No workers running. Start a search."
                  : "No recent activity yet."}
              </p>
            ) : (
              <ul>
                {rows.map((run) => (
                  <EngineRow key={run.id} run={run} now={now} />
                ))}
              </ul>
            )}
          </div>

          <div className="border-t border-white/10 px-4 py-2 text-[10px] text-[#6f675d]">
            Live pipeline activity · updates every 4s
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 rounded-full border border-white/10 bg-[#141210] px-4 py-2.5 text-[#d8d2c8] shadow-xl hover:border-ember/50"
        >
          <span className="relative flex h-2 w-2">
            {active.length > 0 && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                active.length > 0 ? "bg-emerald-400" : "bg-[#6f675d]"
              }`}
            />
          </span>
          <span className="text-[10px] uppercase tracking-[0.16em]">Engine</span>
          <span className="text-[10px] text-[#8d857a]">
            {active.length} live · {queued} queued
          </span>
        </button>
      )}
    </div>
  );
}

function EngineRow({ run, now }: { run: EngineRun; now: number }) {
  const Icon = WORKER_ICONS[run.worker] ?? Sparkles;
  const running = run.status === "RUNNING";
  const failed = run.status === "FAILED";
  return (
    <li>
      <Link
        href={`/dashboard/leads/${run.business_id}`}
        className="flex items-start gap-2.5 rounded-sm px-2.5 py-2 hover:bg-white/5"
      >
        <Icon
          size={13}
          className={`mt-0.5 ${
            running ? "text-ember" : failed ? "text-red-400" : "text-[#6f675d]"
          }`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-[11px] text-[#d8d2c8]">
              {run.business_name ?? run.worker}
            </span>
            {running && (
              <span className="ml-auto shrink-0 text-[10px] text-emerald-400">
                {elapsed(run.started_at, now)}
              </span>
            )}
            {!running && (
              <span className="ml-auto shrink-0 text-[10px] text-[#6f675d]">
                {duration(run.duration_ms)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-[10px] text-[#8d857a]">
            <span className="uppercase tracking-[0.12em]">{run.worker}</span>
            <span
              className={
                running
                  ? "text-emerald-400"
                  : failed
                    ? "text-red-400"
                    : "text-[#6f675d]"
              }
            >
              {run.status.toLowerCase()}
            </span>
            {run.error && (
              <span className="truncate text-red-400/80">{run.error}</span>
            )}
          </div>
          {running && (
            <div className="mt-1 h-0.5 w-full overflow-hidden rounded bg-white/10">
              <div className="h-full w-1/3 animate-[engine-slide_1.4s_ease-in-out_infinite] bg-ember" />
            </div>
          )}
        </div>
      </Link>
    </li>
  );
}
