"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toast } from "sonner";
import {
  ArrowUpRight,
  ExternalLink,
  Filter,
  Loader2,
  Search,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SocialPlatform, SocialProfileWithBusiness } from "@/lib/types";
import {
  SOCIAL_PLATFORM_LABELS,
  SORT_OPTIONS,
  formatCount,
} from "@/lib/format";
import { formatRelative } from "@/lib/utils";
import { useUrlFilters } from "@/lib/use-url-filters";
import { useQuery } from "@/lib/use-query";
import { parsePage } from "@/lib/format";
import { useSearchParams } from "next/navigation";

const PLATFORM_ORDER: SocialPlatform[] = [
  "FACEBOOK",
  "INSTAGRAM",
  "LINKEDIN",
  "TWITTER",
  "YOUTUBE",
  "TIKTOK",
];

const PLATFORM_TONE: Record<SocialPlatform, string> = {
  FACEBOOK: "text-[#1877F2]",
  INSTAGRAM: "text-[#E1306C]",
  LINKEDIN: "text-[#0A66C2]",
  TWITTER: "text-ink",
  YOUTUBE: "text-[#FF0000]",
  TIKTOK: "text-ink",
};

const PLATFORM_BG: Record<SocialPlatform, string> = {
  FACEBOOK: "bg-[#1877F2]/10",
  INSTAGRAM: "bg-[#E1306C]/10",
  LINKEDIN: "bg-[#0A66C2]/10",
  TWITTER: "bg-ink/5",
  YOUTUBE: "bg-[#FF0000]/10",
  TIKTOK: "bg-ink/5",
};

const SORT_SOCIAL_OPTIONS = [
  { value: "followers:desc", label: "Most followers" },
  { value: "followers:asc", label: "Least followers" },
  { value: "posts_count:desc", label: "Most posts" },
  { value: "created_at:desc", label: "Newest" },
  { value: "created_at:asc", label: "Oldest" },
] as const;

export default function SocialsPage() {
  const searchParams = useSearchParams();
  const page = parsePage(searchParams.get("page"));
  const { values, setValues, setPage } = useUrlFilters({
    platform: "",
    q: "",
    min_followers: "",
    sort: "followers:desc",
  });

  const [sortField, sortDir] = (values.sort ?? "followers:desc").split(":" as const);

  const { data, loading, error } = useQuery(
    () =>
      api.listSocialProfiles({
        page,
        limit: 50,
        platform: (values.platform as SocialPlatform) || undefined,
        q: values.q || undefined,
        min_followers: values.min_followers ? parseInt(values.min_followers, 10) : undefined,
        sort_by: sortField as "followers" | "posts_count" | "created_at",
        sort_dir: sortDir as "asc" | "desc",
      }),
    [page, values.platform, values.q, values.min_followers, values.sort],
  );

  const rows = data?.data ?? [];
  const meta = data?.meta;

  // Group by platform for stats
  const grouped = useMemo(() => {
    const map = new Map<SocialPlatform, SocialProfileWithBusiness[]>();
    for (const r of rows) {
      if (!map.has(r.platform)) map.set(r.platform, []);
      map.get(r.platform)!.push(r);
    }
    return map;
  }, [rows]);

  const totalFollowers = useMemo(
    () => rows.reduce((sum, r) => sum + (r.followers ?? 0), 0),
    [rows],
  );

  return (
    <div className="space-y-12 animate-fade-up">
      <header className="space-y-4">
        <p className="status text-ink-mute">
          <span className="status-dot bg-ember animate-pulse-soft" />{" "}
          {meta?.total ?? 0} profiles across all businesses
        </p>
        <h1 className="display text-display-lg text-balance max-w-[20ch]">
          Social presence, all in one place.
        </h1>
        <p className="text-ink-mute max-w-xl">
          Every LinkedIn page, Instagram handle, and YouTube channel the
          workers have surfaced. Filter by platform or follower threshold to
          find businesses with real traction.
        </p>
      </header>

      {/* Stats strip */}
      <section className="grid grid-cols-2 lg:grid-cols-4 border-t border-line">
        <KpiBlock label="Profiles" value={meta?.total ?? 0} loading={loading} />
        <KpiBlock
          label="Platforms"
          value={grouped.size}
          loading={loading}
          hint="In current results"
        />
        <KpiBlock
          label="Total reach"
          value={formatCount(totalFollowers)}
          loading={loading}
          hint="Followers summed"
        />
        <KpiBlock
          label="With bio"
          value={rows.filter((r) => r.bio).length}
          loading={loading}
          hint="Profiles that self-describe"
        />
      </section>

      {/* Platform chips */}
      <section className="border-t border-line pt-8">
        <div className="flex items-center gap-2 mb-4 text-xs font-mono uppercase tracking-wider text-ink-mute">
          <Filter size={12} /> Filter by platform
        </div>
        <div className="flex flex-wrap gap-2">
          <PlatformChip
            label="All"
            count={meta?.total ?? 0}
            active={!values.platform}
            onClick={() => setValues({ platform: "" })}
          />
          {PLATFORM_ORDER.map((p) => (
            <PlatformChip
              key={p}
              label={SOCIAL_PLATFORM_LABELS[p]}
              count={grouped.get(p)?.length ?? 0}
              active={values.platform === p}
              tone={PLATFORM_TONE[p]}
              bg={PLATFORM_BG[p]}
              onClick={() => setValues({ platform: values.platform === p ? "" : p })}
            />
          ))}
        </div>
      </section>

      {/* Search + sort + min followers */}
      <section className="grid md:grid-cols-[1fr_180px_220px] gap-4">
        <label className="relative block">
          <Search
            size={14}
            className="absolute left-0 top-1/2 -translate-y-1/2 text-ink-ghost"
          />
          <input
            type="search"
            placeholder="Search business, username, or bio…"
            value={values.q ?? ""}
            onChange={(e) => setValues({ q: e.target.value })}
            className="w-full bg-transparent border-0 border-b border-ink/30 pl-6 pr-2 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
          />
        </label>
        <label className="block">
          <span className="text-xs font-mono uppercase tracking-wider text-ink-mute block mb-1">
            Sort by
          </span>
          <select
            value={values.sort ?? "followers:desc"}
            onChange={(e) => setValues({ sort: e.target.value })}
            className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember"
          >
            {SORT_SOCIAL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-mono uppercase tracking-wider text-ink-mute block mb-1">
            Min followers
          </span>
          <input
            type="number"
            min={0}
            placeholder="0"
            value={values.min_followers ?? ""}
            onChange={(e) => setValues({ min_followers: e.target.value })}
            className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
          />
        </label>
      </section>

      {/* Table */}
      <section className="border-t border-line overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 size={20} className="animate-spin text-ink-mute" />
          </div>
        ) : error ? (
          <div className="py-16 text-center">
            <p className="display text-display-md mb-3">Couldn&apos;t load</p>
            <p className="text-ink-mute text-sm mb-6 max-w-sm mx-auto">{error}</p>
            <button onClick={() => window.location.reload()} className="btn-outline">
              Reload
            </button>
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            hasAny={(meta?.total ?? 0) > 0}
            onReset={() => setValues({ q: "", platform: "", min_followers: "", sort: "followers:desc" })}
          />
        ) : (
          <>
            <ul className="divide-y divide-line">
              {rows.map((row) => (
                <SocialRowItem key={`${row.business_id}-${row.id}`} row={row} />
              ))}
            </ul>
            {meta && meta.total_pages > 1 && (
              <Pagination
                page={meta.page}
                totalPages={meta.total_pages}
                onChange={setPage}
              />
            )}
          </>
        )}
      </section>
    </div>
  );
}

// ── Building blocks ────────────────────────────────────────────────────────

function PlatformChip({
  label,
  count,
  active,
  tone,
  bg,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  tone?: string;
  bg?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 px-3 py-1.5 text-sm border transition-colors ${
        active
          ? "border-ink bg-ink text-paper"
          : `border-line ${bg ?? "bg-paper-mute/40"} ${tone ?? "text-ink-soft"} hover:border-ink/60`
      }`}
    >
      <span className="font-medium">{label}</span>
      <span
        className={`font-mono text-xs tabular-nums ${
          active ? "text-paper/70" : "text-ink-mute"
        }`}
      >
        {count}
      </span>
    </button>
  );
}

function SocialRowItem({ row }: { row: SocialProfileWithBusiness }) {
  const tone = PLATFORM_TONE[row.platform];
  const initials = (row.username ?? row.business_name ?? "").slice(0, 1).toUpperCase();
  return (
    <li className="grid grid-cols-12 gap-4 items-center py-5 px-1 group">
      {/* Brand + platform */}
      <div className="col-span-12 md:col-span-4 flex items-center gap-3 min-w-0">
        <div
          className={`h-10 w-10 shrink-0 ${PLATFORM_BG[row.platform]} ${tone} flex items-center justify-center font-display text-base`}
        >
          {initials}
        </div>
        <div className="min-w-0">
          <Link
            href={`/dashboard/businesses/${row.business_id}`}
            className="font-display text-lg leading-tight truncate hover:text-ember transition-colors block"
          >
            {row.business_name ?? "—"}
          </Link>
          <p className="text-xs text-ink-mute font-mono truncate">
            {row.business_city ?? "—"} · {SOCIAL_PLATFORM_LABELS[row.platform]}
          </p>
        </div>
      </div>

      {/* Username */}
      <div className="col-span-7 md:col-span-3 min-w-0">
        {row.username ? (
          <a
            href={row.profile_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-mono text-ink-soft hover:text-ember transition-colors truncate flex items-center gap-1"
          >
            @{row.username}
            <ExternalLink size={11} />
          </a>
        ) : (
          <span className="text-sm text-ink-ghost">—</span>
        )}
      </div>

      {/* Followers / posts */}
      <div className="col-span-3 md:col-span-2 text-right">
        <div className="display text-2xl">
          {formatCount(row.followers)}
        </div>
        <div className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
          followers
        </div>
      </div>

      <div className="col-span-2 md:col-span-1 text-right">
        <div className="text-sm font-mono text-ink-soft">
          {formatCount(row.posts_count)}
        </div>
        <div className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
          posts
        </div>
      </div>

      {/* Activity */}
      <div className="hidden md:block md:col-span-2 text-right">
        {row.last_activity_at ? (
          <>
            <div className="text-xs text-ink-soft font-mono">
              {formatRelative(row.last_activity_at)}
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-ink-ghost">
              last post
            </div>
          </>
        ) : (
          <span className="text-xs text-ink-ghost">—</span>
        )}
      </div>

      <div className="col-span-12 md:col-span-0 md:hidden flex items-center justify-end -mt-2">
        <Link
          href={`/dashboard/businesses/${row.business_id}`}
          className="text-xs font-mono uppercase tracking-wider text-ember inline-flex items-center gap-1"
        >
          View <ArrowUpRight size={12} />
        </Link>
      </div>
    </li>
  );
}

function KpiBlock({
  label,
  value,
  hint,
  loading,
}: {
  label: string;
  value: number | string;
  hint?: string;
  loading: boolean;
}) {
  return (
    <div className="py-6 lg:py-8 border-b border-line lg:border-b-0">
      <div className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </div>
      <div className="display text-4xl">
        {loading ? "—" : value}
      </div>
      {hint && <p className="text-xs text-ink-mute mt-1">{hint}</p>}
    </div>
  );
}

function EmptyState({
  hasAny,
  onReset,
}: {
  hasAny: boolean;
  onReset: () => void;
}) {
  return (
    <div className="py-20 text-center">
      <div className="inline-flex h-12 w-12 items-center justify-center bg-paper-mute text-ink-mute mb-4">
        <Users size={20} />
      </div>
      <p className="display text-display-md mb-3">
        {hasAny ? "No matches" : "No social profiles yet"}
      </p>
      <p className="text-ink-mute text-sm max-w-md mx-auto mb-6">
        {hasAny
          ? "Try widening your filters or searching with fewer terms."
          : "Workers surface social profiles after enriching a business. Run a search to get started."}
      </p>
      {hasAny ? (
        <button onClick={onReset} className="btn-outline">
          Reset filters
        </button>
      ) : (
        <Link href="/dashboard/jobs/new" className="btn-solid">
          Start a search
        </Link>
      )}
    </div>
  );
}

function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
}) {
  const canPrev = page > 1;
  const canNext = page < totalPages;
  return (
    <div className="flex items-center justify-between border-t border-line pt-6 mt-6 text-sm">
      <button
        disabled={!canPrev}
        onClick={() => onChange(page - 1)}
        className="btn-ghost disabled:opacity-30 disabled:pointer-events-none"
      >
        ← Previous
      </button>
      <span className="font-mono text-xs uppercase tracking-wider text-ink-mute">
        Page {page} of {totalPages}
      </span>
      <button
        disabled={!canNext}
        onClick={() => onChange(page + 1)}
        className="btn-ghost disabled:opacity-30 disabled:pointer-events-none"
      >
        Next →
      </button>
    </div>
  );
}
