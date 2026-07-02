"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { toast } from "sonner";
import { ArrowUpRight, Loader2, Search, Download, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { Business, WebsiteStatus } from "@/lib/types";
import { useUrlFilters } from "@/lib/use-url-filters";
import {
  WEBSITE_STATUS_COLORS,
  WEBSITE_STATUS_LABELS,
  SORT_OPTIONS,
  formatCount,
  formatLocation,
  formatRating,
  parsePage,
  parseRating,
  type SortValue,
} from "@/lib/format";
import { BusinessFilters } from "./_components/business-filters";

const LIMIT = 50;

type Filters = {
  name: string;
  city: string;
  country: string;
  category: string;
  website_status: WebsiteStatus | "";
  min_rating: string;
  max_rating: string;
  sort: SortValue;
};

const DEFAULTS: Filters = {
  name: "",
  city: "",
  country: "",
  category: "",
  website_status: "",
  min_rating: "",
  max_rating: "",
  sort: "created_at:desc",
};

export default function BusinessesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { values, setValues, setPage } = useUrlFilters(DEFAULTS);

  const page = parsePage(searchParams.get("page"));

  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState(values.name ?? "");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  // Sync draft when URL changes (e.g. via reset)
  useEffect(() => {
    setSearchDraft(values.name ?? "");
  }, [values.name]);

  const apiFilters = useMemo(
    () => ({
      page,
      limit: LIMIT,
      name: values.name || undefined,
      city: values.city || undefined,
      country: values.country || undefined,
      category: values.category || undefined,
      website_status:
        (values.website_status as WebsiteStatus | "") || undefined,
      min_rating: parseRating(values.min_rating),
      max_rating: parseRating(values.max_rating),
    }),
    [page, values],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listBusinesses(apiFilters)
      .then((res) => {
        if (cancelled) return;
        setBusinesses(res.data);
        setTotal(res.meta.total);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Failed to load";
        setError(msg);
        toast.error(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiFilters]);

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  // Client-side sort
  const sorted = useMemo(() => {
    const [field, dir] = (values.sort ?? "created_at:desc").split(":" as const);
    const copy = [...businesses];
    copy.sort((a, b) => {
      let av: number | string = "";
      let bv: number | string = "";
      if (field === "name") {
        av = a.name.toLowerCase();
        bv = b.name.toLowerCase();
      } else if (field === "rating") {
        av = a.rating ?? -1;
        bv = b.rating ?? -1;
      } else if (field === "review_count") {
        av = a.review_count ?? 0;
        bv = b.review_count ?? 0;
      } else {
        av = a.created_at;
        bv = b.created_at;
      }
      if (av < bv) return dir === "asc" ? -1 : 1;
      if (av > bv) return dir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [businesses, values.sort]);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    setValues({ name: searchDraft });
  }

  const allSelected = sorted.length > 0 && sorted.every((b) => selected.has(b.id));

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sorted.map((b) => b.id)));
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function bulkReEnrich() {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    setBulkLoading(true);
    try {
      await api.bulkReEnrich(ids);
      toast.success(`Re-enrich queued for ${ids.length} businesses`);
      setSelected(new Set());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Bulk re-enrich failed");
    } finally {
      setBulkLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10 animate-fade-up">
      {/* Sidebar filters */}
      <BusinessFilters resultCount={loading ? undefined : total} />

      {/* Main column */}
      <div className="space-y-8 min-w-0">
        <header>
          <p className="status text-ink-mute mb-3">
            <span className="status-dot bg-ember" /> {total.toLocaleString()}{" "}
            {total === 1 ? "business" : "businesses"}
          </p>
          <h1 className="display text-display-lg">Businesses</h1>
          <p className="text-ink-mute mt-2">
            All businesses discovered across your search jobs.
          </p>
        </header>

        {/* Search bar + sort */}
        <div className="flex items-center gap-4 border-b border-line pb-3">
          <form
            onSubmit={onSearch}
            className="flex-1 flex items-center gap-3"
          >
            <Search size={16} className="text-ink-mute" />
            <input
              type="text"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              placeholder="Search by name…"
              className="flex-1 bg-transparent border-0 outline-none text-base placeholder:text-ink-ghost"
            />
            <button type="submit" className="btn-ghost text-xs">
              Search
            </button>
          </form>
          <label className="shrink-0">
            <span className="sr-only">Sort by</span>
            <select
              value={values.sort ?? "created_at:desc"}
              onChange={(e) => setValues({ sort: e.target.value as SortValue })}
              className="bg-transparent border-0 border-b border-ink/30 px-0 py-1 text-xs font-mono uppercase tracking-wider text-ink-mute focus:outline-none focus:border-ember"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* Results */}
        <section>
          {loading ? (
            <Skeleton />
          ) : error ? (
            <ErrorState message={error} onRetry={() => router.refresh()} />
          ) : businesses.length === 0 ? (
            <EmptyState />
          ) : (
            <>
              {/* Bulk action bar */}
              {selected.size > 0 && (
                <div className="flex items-center gap-4 py-3 px-2 bg-ink/5 border-y border-line text-sm">
                  <span className="font-mono text-xs">
                    {selected.size} selected
                  </span>
                  <button
                    onClick={bulkReEnrich}
                    disabled={bulkLoading}
                    className="btn-ghost text-xs inline-flex items-center gap-1.5"
                  >
                    {bulkLoading ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <RefreshCw size={12} />
                    )}
                    Re-enrich
                  </button>
                  <button
                    onClick={() => setSelected(new Set())}
                    className="btn-ghost text-xs text-ink-mute"
                  >
                    Clear
                  </button>
                </div>
              )}

              <ul className="divide-y divide-line border-y border-line">
                {/* Select all header */}
                <li className="grid grid-cols-12 gap-4 items-center py-3 px-2 border-b border-line">
                  <div className="col-span-1">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="accent-ember"
                    />
                  </div>
                  <div className="col-span-11 text-xs font-mono uppercase tracking-wider text-ink-mute">
                    Select all
                  </div>
                </li>
                {sorted.map((b) => (
                  <BusinessRow
                    key={b.id}
                    business={b}
                    selected={selected.has(b.id)}
                    onSelect={() => toggleSelect(b.id)}
                  />
                ))}
              </ul>
              {totalPages > 1 && (
                <Pagination
                  page={page}
                  totalPages={totalPages}
                  onChange={setPage}
                />
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function BusinessRow({
  business,
  selected,
  onSelect,
}: {
  business: Business;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li className="group">
      <div className="grid grid-cols-12 gap-4 items-center py-5 px-2 hover:bg-paper-mute/40 transition-colors">
        <div className="col-span-1">
          <input
            type="checkbox"
            checked={selected}
            onChange={onSelect}
            onClick={(e) => e.stopPropagation()}
            className="accent-ember"
          />
        </div>
        <Link
          href={`/dashboard/businesses/${business.id}`}
          className="col-span-11 grid grid-cols-11 gap-4 items-center min-w-0"
        >
        <div className="col-span-12 md:col-span-5 min-w-0">
          <div className="display text-lg leading-tight truncate">
            {business.name}
          </div>
          <div className="text-xs text-ink-mute font-mono mt-1 truncate">
            {business.category ?? "Uncategorized"} ·{" "}
            {formatLocation(business)}
          </div>
        </div>

        <div className="col-span-6 md:col-span-2 flex items-center gap-1.5">
          <span className="font-display text-lg">
            {formatRating(business.rating)}
          </span>
          <span className="text-xs text-ink-mute font-mono">
            ({formatCount(business.review_count)})
          </span>
        </div>

        <div className="col-span-6 md:col-span-2">
          <WebsiteStatusPill status={business.website_status} />
        </div>

        <div className="col-span-8 md:col-span-2 text-xs text-ink-mute font-mono uppercase tracking-wider">
          {business.source?.replace("_", " ").toLowerCase() ?? "—"}
        </div>

        <div className="col-span-4 md:col-span-1 flex justify-end">
          <ArrowUpRight
            size={16}
            className="text-ink-ghost group-hover:text-ember transition-colors"
          />
        </div>
        </Link>
      </div>
    </li>
  );
}

function WebsiteStatusPill({ status }: { status: WebsiteStatus }) {
  return (
    <span className="status text-ink-mute">
      <span className={`status-dot ${WEBSITE_STATUS_COLORS[status]}`} />
      {WEBSITE_STATUS_LABELS[status].toLowerCase()}
    </span>
  );
}

function Skeleton() {
  return (
    <div className="border-y border-line">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-12 gap-4 items-center py-5 px-2 border-b border-line last:border-b-0"
        >
          <div className="col-span-5 space-y-2">
            <div className="h-5 w-3/4 bg-paper-mute animate-pulse-soft" />
            <div className="h-3 w-1/2 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-5 w-12 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-3 w-16 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-3 w-14 bg-paper-mute animate-pulse-soft" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="py-20 text-center border-y border-line">
      <p className="display text-display-md mb-3">No businesses match</p>
      <p className="text-ink-mute text-sm max-w-sm mx-auto mb-8">
        Try adjusting your filters, or run a search job to discover new
        businesses.
      </p>
      <Link href="/dashboard/jobs/new" className="btn-solid">
        New search <ArrowUpRight size={16} />
      </Link>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="py-20 text-center border-y border-line">
      <p className="display text-display-md mb-3">Couldn't load</p>
      <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">{message}</p>
      <button onClick={onRetry} className="btn-outline">
        Try again
      </button>
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