"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowUpRight, Loader2, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { Lead, LeadGrade, WebsiteStatus } from "@/lib/types";
import { useUrlFilters } from "@/lib/use-url-filters";
import {
  LEAD_GRADES,
  LEAD_SORT_OPTIONS,
  WEBSITE_STATUS_LABELS,
  formatCount,
  formatLocation,
  formatRating,
  parsePage,
  parseRating,
  type SortValue,
} from "@/lib/format";
import { ScorePill } from "@/components/score-breakdown";
import { PhoneTypeBadge, VerificationBadge } from "@/components/verification-badge";

const LIMIT = 50;

type Filters = {
  grade: LeadGrade | "";
  score_min: string;
  score_max: string;
  website_status: WebsiteStatus | "";
  best_contact_method: string;
  city: string;
  country: string;
  verified_email: string;
  has_mobile: string;
  sort: SortValue;
};

const DEFAULTS: Filters = {
  grade: "",
  score_min: "",
  score_max: "",
  website_status: "",
  best_contact_method: "",
  city: "",
  country: "",
  verified_email: "",
  has_mobile: "",
  sort: "score_max:desc",
};

const CONTACT_METHODS = ["email", "phone", "form", "social"];

export default function LeadsPage() {
  const searchParams = useSearchParams();
  const page = parsePage(searchParams.get("page"));
  const { values, setValues, setPage } = useUrlFilters(DEFAULTS);

  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<{
    total_count?: number;
    verified_email_count?: number;
    checked_email_count?: number;
    mobile_count?: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  const apiFilters = useMemo(
    () => ({
      page,
      limit: LIMIT,
      grade: (values.grade as LeadGrade | "") || undefined,
      score_min: parseRating(values.score_min),
      score_max: parseRating(values.score_max),
      website_status:
        (values.website_status as WebsiteStatus | "") || undefined,
      best_contact_method: values.best_contact_method || undefined,
      city: values.city || undefined,
      country: values.country || undefined,
      verified_email: values.verified_email === "1" ? true : undefined,
      has_mobile: values.has_mobile === "1" ? true : undefined,
      include_stats: true,
    }),
    [page, values],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listLeads(apiFilters)
      .then((res) => {
        if (cancelled) return;
        setLeads(res.data);
        setTotal(res.meta.total);
        setStats({
          total_count: res.meta.total_count,
          verified_email_count: res.meta.verified_email_count,
          checked_email_count: res.meta.checked_email_count,
          mobile_count: res.meta.mobile_count,
        });
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
    const [field, dir] = (values.sort ?? "score:desc").split(":" as const);
    const copy = [...leads];
    copy.sort((a, b) => {
      let av: number | string = "";
      let bv: number | string = "";
      if (field === "score") {
        av = a.lead_score?.score ?? 0;
        bv = b.lead_score?.score ?? 0;
      } else if (field === "grade") {
        const gradeOrder: Record<string, number> = { "A+": 6, A: 5, B: 4, C: 3, D: 2, F: 1 };
        av = gradeOrder[a.lead_score?.grade ?? "F"] ?? 0;
        bv = gradeOrder[b.lead_score?.grade ?? "F"] ?? 0;
      } else if (field === "name") {
        av = a.business.name.toLowerCase();
        bv = b.business.name.toLowerCase();
      } else {
        av = a.business.created_at;
        bv = b.business.created_at;
      }
      if (av < bv) return dir === "asc" ? -1 : 1;
      if (av > bv) return dir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [leads, values.sort]);

  const allSelected = sorted.length > 0 && sorted.every((l) => selected.has(l.business.id));

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sorted.map((l) => l.business.id)));
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

  // Quick counts per grade (top of page)
  const gradeCounts = useMemo(() => {
    const counts: Partial<Record<LeadGrade, number>> = {};
    for (const lead of leads) {
      const g = lead.lead_score?.grade;
      if (g) counts[g] = (counts[g] ?? 0) + 1;
    }
    return counts;
  }, [leads]);

  return (
    <div className="space-y-12 animate-fade-up">
      <header>
        <p className="status text-ink-mute mb-3">
          <span className="status-dot bg-ember animate-pulse-soft" />{" "}
          {total.toLocaleString()} {total === 1 ? "lead" : "leads"} scored
        </p>
        <h1 className="display text-display-lg">Leads</h1>
        <p className="text-ink-mute mt-2 max-w-lg">
          Businesses with calculated outreach scores. Filter by grade to find
          your highest-priority opportunities first.
        </p>
      </header>

      {/* Filters strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 border-y border-line py-6">
        <FilterSelect
          label="Grade"
          value={values.grade ?? ""}
          onChange={(v) => setValues({ grade: v as LeadGrade | "" })}
          options={[
            { value: "", label: "Any" },
            ...LEAD_GRADES.map((g) => ({ value: g, label: g })),
          ]}
        />
        <FilterSelect
          label="Website"
          value={values.website_status ?? ""}
          onChange={(v) => setValues({ website_status: v as WebsiteStatus | "" })}
          options={[
            { value: "", label: "Any" },
            { value: "FOUND", label: "Has website" },
            { value: "NOT_FOUND", label: "No website" },
            { value: "INVALID", label: "Invalid" },
          ]}
        />
        <FilterSelect
          label="Best contact"
          value={values.best_contact_method ?? ""}
          onChange={(v) => setValues({ best_contact_method: v })}
          options={[
            { value: "", label: "Any" },
            ...CONTACT_METHODS.map((m) => ({ value: m, label: m })),
          ]}
        />
        <NumberInput
          label="Score min"
          value={values.score_min ?? ""}
          onChange={(v) => setValues({ score_min: v })}
          min={0}
          max={100}
        />
        <NumberInput
          label="Score max"
          value={values.score_max ?? ""}
          onChange={(v) => setValues({ score_max: v })}
          min={0}
          max={100}
        />
        <TextInput
          label="City"
          value={values.city ?? ""}
          onChange={(v) => setValues({ city: v })}
        />
        <TextInput
          label="Country"
          value={values.country ?? ""}
          onChange={(v) => setValues({ country: v.toUpperCase() })}
          maxLength={2}
        />
        <FilterSelect
          label="Sort"
          value={values.sort ?? "score:desc"}
          onChange={(v) => setValues({ sort: v as SortValue })}
          options={[
            ...LEAD_SORT_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
          ]}
        />
      </div>

      {/* Quality filters */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 pb-6">
        <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            className="accent-ember"
            checked={values.verified_email === "1"}
            onChange={(e) =>
              setValues({ verified_email: e.target.checked ? "1" : "" })
            }
          />
          Verified email only
        </label>
        <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            className="accent-ember"
            checked={values.has_mobile === "1"}
            onChange={(e) =>
              setValues({ has_mobile: e.target.checked ? "1" : "" })
            }
          />
          Mobile number only
        </label>
        {stats && (
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-ink-mute">
            <span className="rounded-full border border-line px-3 py-1">
              <strong className="text-ink">{stats.total_count ?? 0}</strong> matched
            </span>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-800">
              <strong>{stats.verified_email_count ?? 0}</strong> verified email
            </span>
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-amber-800">
              <strong>{stats.checked_email_count ?? 0}</strong> domain-checked
            </span>
            <span className="rounded-full border border-line px-3 py-1">
              <strong className="text-ink">{stats.mobile_count ?? 0}</strong> mobile
            </span>
          </div>
        )}
      </div>

      {/* Results */}
      <section>
        {loading ? (
          <Skeleton />
        ) : error ? (
          <div className="py-20 text-center border-y border-line">
            <p className="display text-display-md mb-3">Couldn't load</p>
            <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">{error}</p>
          </div>
        ) : leads.length === 0 ? (
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
              {sorted.map((lead) => (
                <LeadRow
                  key={lead.business.id}
                  lead={lead}
                  countForGrade={
                    lead.lead_score?.grade
                      ? gradeCounts[lead.lead_score.grade]
                      : undefined
                  }
                  selected={selected.has(lead.business.id)}
                  onSelect={() => toggleSelect(lead.business.id)}
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
  );
}

function LeadRow({
  lead,
  countForGrade,
  selected,
  onSelect,
}: {
  lead: Lead;
  countForGrade?: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const { business, lead_score } = lead;
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
          href={`/dashboard/leads/${business.id}`}
          className="col-span-11 grid grid-cols-11 gap-4 items-center min-w-0"
        >
        <div className="col-span-12 md:col-span-4 min-w-0">
          <div className="display text-lg leading-tight truncate">
            {business.name}
          </div>
          <div className="text-xs text-ink-mute font-mono mt-1 truncate">
            {business.category ?? "Uncategorized"} · {formatLocation(business)}
          </div>
          <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
            <VerificationBadge verification={lead.contacts.find((c) => c.type === "EMAIL")?.verification} />
            <PhoneTypeBadge lineType={lead.contacts.find((c) => c.type === "PHONE")?.verification?.line_type} />
          </div>
        </div>

        <div className="col-span-6 md:col-span-3">
          <ScorePill score={lead_score?.score} grade={lead_score?.grade ?? null} />
        </div>

        <div className="col-span-3 md:col-span-2">
          <div className="flex items-center gap-1.5">
            <span className="font-display text-lg">
              {formatRating(business.rating)}
            </span>
            <span className="text-xs text-ink-mute font-mono">
              ({formatCount(business.review_count)})
            </span>
          </div>
        </div>

        <div className="col-span-6 md:col-span-2 text-xs text-ink-mute font-mono uppercase tracking-wider truncate">
          {lead_score?.best_contact_method ?? "—"}
        </div>

        <div className="col-span-3 md:col-span-1 flex justify-end">
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

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div>
      <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  maxLength?: number;
}) {
  return (
    <div>
      <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm placeholder:text-ink-ghost focus:outline-none focus:border-ember transition-colors"
      />
    </div>
  );
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div>
      <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        min={min}
        max={max}
        className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm placeholder:text-ink-ghost focus:outline-none focus:border-ember transition-colors"
      />
    </div>
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
          <div className="col-span-4 space-y-2">
            <div className="h-5 w-3/4 bg-paper-mute animate-pulse-soft" />
            <div className="h-3 w-1/2 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-3">
            <div className="h-6 w-16 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-5 w-14 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-3 w-20 bg-paper-mute animate-pulse-soft" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="py-20 text-center border-y border-line">
      <p className="display text-display-md mb-3">No scored leads yet</p>
      <p className="text-ink-mute text-sm max-w-sm mx-auto mb-8">
        Leads appear here once workers finish scoring discovered businesses.
        Try lowering the score filter or running more searches.
      </p>
      <Link href="/dashboard/jobs/new" className="btn-solid">
        New search <ArrowUpRight size={16} />
      </Link>
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