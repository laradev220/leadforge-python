"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  ArrowUpRight,
  ArrowLeft,
  Loader2,
  MapPin,
  Globe,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SearchJobWithBusinesses, SearchJobStatus } from "@/lib/types";
import { formatRelative } from "@/lib/utils";
import { formatRating, formatLocation } from "@/lib/format";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [job, setJob] = useState<SearchJobWithBusinesses | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getSearchJob(id);
      setJob(res.data);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load job";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh while active
  useEffect(() => {
    if (!job) return;
    const isActive = job.status === "RUNNING" || job.status === "PENDING";
    if (!isActive) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [job, load]);

  async function cancel() {
    if (!job) return;
    try {
      await api.cancelSearchJob(job.id);
      toast.success("Job cancelled");
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 size={20} className="animate-spin text-ink-mute" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="py-20 text-center">
        <p className="display text-display-md mb-3">Couldn&apos;t load job</p>
        <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">
          {error ?? "Job not found"}
        </p>
        <button onClick={() => router.back()} className="btn-outline">
          Go back
        </button>
      </div>
    );
  }

  const businesses = job.businesses ?? [];
  const isActive = job.status === "RUNNING" || job.status === "PENDING";

  return (
    <div className="space-y-10 animate-fade-up">
      {/* Back link */}
      <Link
        href="/dashboard/jobs"
        className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-ink-mute hover:text-ink transition-colors"
      >
        <ArrowLeft size={14} /> All jobs
      </Link>

      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="display text-display-lg">{job.keyword}</h1>
            <div className="flex items-center gap-2 text-ink-mute mt-2">
              <MapPin size={14} />
              <span className="text-sm">{job.location}</span>
              {job.country && (
                <>
                  <span className="text-ink-ghost">·</span>
                  <span className="text-sm font-mono">{job.country}</span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusPill status={job.status} />
            {isActive && (
              <button
                onClick={cancel}
                className="text-ink-mute hover:text-ember transition-colors"
                aria-label="Cancel job"
              >
                <X size={18} />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Stats strip */}
      <section className="grid grid-cols-2 lg:grid-cols-4 border-t border-line">
        <StatBlock
          label="Discovered"
          value={job.total_discovered}
          loading={false}
        />
        <StatBlock
          label="Enriched"
          value={job.total_enriched}
          loading={false}
        />
        <StatBlock
          label="Created"
          value={formatRelative(job.created_at)}
          loading={false}
          small
        />
        <StatBlock
          label="Completed"
          value={
            job.completed_at
              ? formatRelative(job.completed_at)
              : job.started_at
                ? "In progress…"
                : "—"
          }
          loading={false}
          small
        />
      </section>

      {/* Discovered businesses */}
      <section className="border-t border-line pt-8">
        <h2 className="display text-display-md mb-6">
          Discovered businesses
          {businesses.length > 0 && (
            <span className="text-ink-mute ml-3">({businesses.length})</span>
          )}
        </h2>

        {businesses.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-ink-mute text-sm">
              {isActive
                ? "Workers are still discovering businesses…"
                : "No businesses were discovered for this search."}
            </p>
          </div>
        ) : (
          <ul className="border-t border-line">
            {businesses.map((entry) => {
              const b = entry.business;
              return (
                <li
                  key={entry.id}
                  className="border-b border-line"
                >
                  <Link
                    href={`/dashboard/businesses/${b.id}`}
                    className="grid grid-cols-12 gap-4 items-center py-5 px-2 hover:bg-paper-mute/40 transition-colors group"
                  >
                    <div className="col-span-12 md:col-span-4 min-w-0">
                      <div className="display text-lg leading-tight truncate group-hover:text-ember transition-colors">
                        {b.name}
                      </div>
                      <div className="text-xs text-ink-mute font-mono mt-1 truncate">
                        {b.category ?? "Uncategorized"}
                      </div>
                    </div>
                    <div className="col-span-6 md:col-span-3 text-sm text-ink-soft truncate">
                      {formatLocation(b)}
                    </div>
                    <div className="col-span-3 md:col-span-2">
                      <div className="flex items-center gap-1.5">
                        <span className="font-display text-lg">
                          {formatRating(b.rating)}
                        </span>
                        {b.review_count != null && (
                          <span className="text-xs text-ink-mute font-mono">
                            ({b.review_count})
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="col-span-3 md:col-span-2">
                      <WebsitePill status={b.website_status} />
                    </div>
                    <div className="col-span-12 md:col-span-1 flex justify-end">
                      <ArrowUpRight
                        size={16}
                        className="text-ink-ghost group-hover:text-ember transition-colors"
                      />
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function StatBlock({
  label,
  value,
  loading,
  small,
}: {
  label: string;
  value: number | string;
  loading: boolean;
  small?: boolean;
}) {
  return (
    <div className="py-6 lg:py-8 border-b border-line lg:border-b-0">
      <div className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </div>
      <div className={small ? "text-sm font-mono" : "display text-4xl"}>
        {loading ? "—" : value}
      </div>
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

function WebsitePill({ status }: { status: string }) {
  const colors: Record<string, string> = {
    UNKNOWN: "bg-ink-ghost",
    FOUND: "bg-moss",
    NOT_FOUND: "bg-ember",
    INVALID: "bg-red-700",
  };
  const labels: Record<string, string> = {
    UNKNOWN: "unknown",
    FOUND: "has website",
    NOT_FOUND: "no website",
    INVALID: "invalid",
  };
  return (
    <span className="status text-ink-mute text-xs">
      <span className={`status-dot ${colors[status] ?? "bg-ink-ghost"}`} />
      {labels[status] ?? status}
    </span>
  );
}
