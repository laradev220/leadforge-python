"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SearchJob } from "@/lib/types";
import { ArrowUpRight, Compass, Loader2 } from "lucide-react";
import { formatRelative } from "@/lib/utils";

export default function DashboardOverview() {
  const [jobs, setJobs] = useState<SearchJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listSearchJobs(1, 5)
      .then((res) => setJobs(res.data))
      .finally(() => setLoading(false));
  }, []);

  const running = jobs.filter((j) => j.status === "RUNNING").length;
  const completed = jobs.filter((j) => j.status === "COMPLETED").length;
  const discovered = jobs.reduce((sum, j) => sum + j.total_discovered, 0);

  return (
    <div className="space-y-16 animate-fade-up">
      <header>
        <p className="status text-ink-mute mb-4">
          <span className="status-dot bg-ember animate-pulse-soft" /> Welcome back
        </p>
        <h1 className="display text-display-lg text-balance max-w-[20ch]">
          Discover businesses worth your time.
        </h1>
      </header>

      {/* Stat strip */}
      <section className="grid grid-cols-1 md:grid-cols-3 border-t border-line">
        {[
          { label: "Recent jobs", value: jobs.length, suffix: "" },
          { label: "Running now", value: running, suffix: "" },
          { label: "Businesses found", value: discovered, suffix: "" },
        ].map((stat, i) => (
          <div
            key={stat.label}
            className={`py-8 ${i > 0 ? "md:border-l border-line md:pl-8" : ""}`}
          >
            <div className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
              {stat.label}
            </div>
            <div className="display text-5xl">
              {loading ? "—" : stat.value}
            </div>
          </div>
        ))}
      </section>

      {/* Quick start */}
      <section className="grid md:grid-cols-2 gap-12">
        <div>
          <h2 className="display text-display-md mb-4">Start a search</h2>
          <p className="text-ink-mute mb-8 max-w-md">
            Spin up a discovery worker with a keyword and a location. Workers
            crawl Google Maps and directories, then enrich every match.
          </p>
          <Link href="/dashboard/jobs/new" className="btn-solid">
            New search <ArrowUpRight size={16} />
          </Link>
        </div>

        <div>
          <h2 className="display text-display-md mb-4">Recent activity</h2>
          {loading ? (
            <div className="text-sm text-ink-mute flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-sm text-ink-mute">
              No searches yet. Run your first one to see activity here.
            </div>
          ) : (
            <ul className="space-y-3">
              {jobs.map((job) => (
                <li key={job.id} className="flex items-center justify-between border-b border-line py-3">
                  <div className="min-w-0">
                    <div className="font-display text-lg truncate">
                      {job.keyword} · {job.location}
                    </div>
                    <div className="text-xs text-ink-mute font-mono">
                      {formatRelative(job.created_at)} · {job.total_discovered} found
                    </div>
                  </div>
                  <StatusPill status={job.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="border-t border-line pt-8 flex items-center gap-4 text-sm text-ink-mute">
        <Compass size={16} className="text-ember" />
        Pro tip — workers run async. You can close this tab and come back later.
      </section>
    </div>
  );
}

function StatusPill({ status }: { status: SearchJob["status"] }) {
  const colors: Record<SearchJob["status"], string> = {
    PENDING: "bg-ink-ghost",
    RUNNING: "bg-ember animate-pulse-soft",
    COMPLETED: "bg-moss",
    FAILED: "bg-red-700",
    CANCELLED: "bg-ink-ghost",
  };
  return (
    <span className="status text-ink-mute">
      <span className={`status-dot ${colors[status]}`} />
      {status.toLowerCase()}
    </span>
  );
}