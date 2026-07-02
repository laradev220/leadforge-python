"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { SearchJob, SearchJobStatus } from "@/lib/types";
import { formatRelative } from "@/lib/utils";
import { ArrowUpRight, Loader2, X } from "lucide-react";

const STATUSES: (SearchJobStatus | "ALL")[] = [
  "ALL",
  "PENDING",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
];

export default function JobsPage() {
  const [jobs, setJobs] = useState<SearchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<SearchJobStatus | "ALL">("ALL");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listSearchJobs(1, 100, filter === "ALL" ? undefined : filter);
      setJobs(res.data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh while there are running/pending jobs
  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === "RUNNING" || j.status === "PENDING");
    if (!hasActive) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [jobs, load]);

  async function cancel(id: string) {
    try {
      await api.cancelSearchJob(id);
      toast.success("Job cancelled");
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  return (
    <div className="space-y-10 animate-fade-up">
      <header className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <p className="status text-ink-mute mb-3">
            <span className="status-dot bg-ember" /> {jobs.length} {jobs.length === 1 ? "job" : "jobs"}
          </p>
          <h1 className="display text-display-lg">Search jobs</h1>
          <p className="text-ink-mute mt-2 max-w-md">
            Every search runs async. Workers enrich each result with contact,
            social, and website data.
          </p>
        </div>
        <Link href="/dashboard/jobs/new" className="btn-solid">
          New search <ArrowUpRight size={16} />
        </Link>
      </header>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-2 border-t border-line pt-6">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-4 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
              filter === s
                ? "bg-ink text-paper"
                : "text-ink-mute hover:text-ink"
            }`}
          >
            {s.toLowerCase()}
          </button>
        ))}
      </div>

      {/* List */}
      <section>
        {loading && jobs.length === 0 ? (
          <div className="text-sm text-ink-mute flex items-center gap-2 py-12 justify-center">
            <Loader2 size={14} className="animate-spin" /> Loading…
          </div>
        ) : jobs.length === 0 ? (
          <div className="py-20 text-center">
            <p className="display text-display-md mb-3">No jobs yet</p>
            <p className="text-ink-mute mb-8">Run your first search to populate this list.</p>
            <Link href="/dashboard/jobs/new" className="btn-solid">
              New search <ArrowUpRight size={16} />
            </Link>
          </div>
        ) : (
          <ul className="border-t border-line">
            {jobs.map((job) => (
              <li
                key={job.id}
                className="border-b border-line"
              >
                <div className="grid grid-cols-12 gap-4 items-center py-5 px-2 hover:bg-paper-mute/40 transition-colors group">
                  <Link
                    href={`/dashboard/jobs/${job.id}`}
                    className="col-span-12 md:col-span-5 min-w-0 block"
                  >
                    <div className="display text-xl truncate group-hover:text-ember transition-colors">
                      {job.keyword}
                    </div>
                    <div className="text-sm text-ink-mute truncate">
                      {job.location}{job.country ? ` · ${job.country}` : ""}
                    </div>
                  </Link>
                  <div className="col-span-6 md:col-span-2 font-mono text-xs text-ink-mute">
                    {formatRelative(job.created_at)}
                  </div>
                  <div className="col-span-6 md:col-span-2">
                    <div className="font-display text-2xl">{job.total_discovered}</div>
                    <div className="text-xs text-ink-mute font-mono uppercase tracking-wider">found</div>
                  </div>
                  <div className="col-span-8 md:col-span-2">
                    <StatusPill status={job.status} />
                  </div>
                  <div className="col-span-4 md:col-span-1 flex justify-end">
                    {(job.status === "RUNNING" || job.status === "PENDING") && (
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          cancel(job.id);
                        }}
                        className="text-ink-mute hover:text-ember transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                        aria-label="Cancel job"
                      >
                        <X size={18} />
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function StatusPill({ status }: { status: SearchJobStatus }) {
  const colors: Record<SearchJobStatus, string> = {
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