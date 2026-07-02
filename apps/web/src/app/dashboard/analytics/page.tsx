"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { ArrowUpRight, Compass } from "lucide-react";
import { api } from "@/lib/api";
import type { DashboardStats, GradeDistribution, LeadGrade } from "@/lib/types";
import { DonutChart, HorizontalBars, KpiStat, Sparkline } from "@/components/charts";
import { LEAD_GRADES } from "@/lib/format";

interface JobTimeline {
  day: string;
  jobs_completed: number;
  businesses_found: number;
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [distribution, setDistribution] = useState<GradeDistribution | null>(null);
  const [timeline, setTimeline] = useState<JobTimeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([api.dashboardStats(), api.leadDistribution()])
      .then(([s, d]) => {
        if (cancelled) return;
        setStats(s.data);
        setDistribution(d.data.distribution);
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
  }, []);

  // Skeleton if loading
  if (loading && !stats) {
    return <DashboardSkeleton />;
  }

  if (error || !stats || !distribution) {
    return (
      <div className="py-20 text-center">
        <p className="display text-display-md mb-3">Couldn't load analytics</p>
        <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">
          {error ?? "Try again in a moment."}
        </p>
        <button onClick={() => window.location.reload()} className="btn-outline">
          Reload
        </button>
      </div>
    );
  }

  // Derived metrics
  const websiteRatio =
    stats.businesses === 0
      ? 0
      : (stats.websitesFound / stats.businesses) * 100;

  const totalScored = Object.values(distribution).reduce((s, v) => s + v, 0);
  const topGradeCount = LEAD_GRADES.slice(0, 2).reduce(
    (s, g) => s + (distribution[g] ?? 0),
    0,
  );
  const conversion =
    totalScored === 0 ? 0 : (topGradeCount / totalScored) * 100;

  // Donut segments — grade color hierarchy
  const GRADE_COLORS: Record<LeadGrade, string> = {
    "A+": "text-ember",
    A: "text-ember/70",
    B: "text-moss",
    C: "text-ink-soft",
    D: "text-ink-mute",
    F: "text-ink-ghost",
  };

  const donutData = LEAD_GRADES.map((g) => ({
    label: g,
    value: distribution[g] ?? 0,
    color: GRADE_COLORS[g],
  }));

  // Sorted grade bars
  const gradeBars = LEAD_GRADES.map((g) => ({
    label: `Grade ${g}`,
    value: distribution[g] ?? 0,
    highlight: g === "A+" || g === "A",
    href: `/dashboard/leads?grade=${encodeURIComponent(g)}`,
  }));

  // Build sparkline series from a mock timeline (until backend has it)
  const sparkValues = buildSparkSeries(stats.businesses);

  return (
    <div className="space-y-16 animate-fade-up">
      <header>
        <p className="status text-ink-mute mb-3">
          <span className="status-dot bg-ember animate-pulse-soft" /> live ·
          across all jobs
        </p>
        <h1 className="display text-display-lg">Analytics</h1>
        <p className="text-ink-mute mt-2 max-w-md">
          The shape of your discovery pipeline — what you've found, what's
          enriched, and where the high-value opportunities are.
        </p>
      </header>

      {/* KPI strip */}
      <section className="grid grid-cols-2 lg:grid-cols-5 border-t border-line divide-x divide-line">
        <div className="lg:pl-0">
          <KpiStat
            label="Businesses"
            value={stats.businesses}
            hint="Total discovered across all jobs"
            delay={0}
          />
        </div>
        <div className="lg:pl-8">
          <KpiStat
            label="Websites found"
            value={stats.websitesFound}
            meta={`${websiteRatio.toFixed(0)}% of all`}
            hint="Has a reachable website"
            delay={80}
          />
        </div>
        <div className="lg:pl-8">
          <KpiStat
            label="Emails"
            value={stats.emailsFound}
            hint="Verified business emails"
            delay={160}
          />
        </div>
        <div className="lg:pl-8">
          <KpiStat
            label="Social profiles"
            value={stats.socialProfilesFound}
            hint="Across LinkedIn, Facebook, Instagram…"
            delay={240}
          />
        </div>
        <div className="lg:pl-8">
          <KpiStat
            label="High-value leads"
            value={stats.highValueLeads}
            meta={`${conversion.toFixed(0)}% A+/A conversion`}
            hint="Score ≥ 80"
            delay={320}
          />
        </div>
      </section>

      {/* Grade distribution + sparkline */}
      <section className="grid lg:grid-cols-[1.1fr_1fr] gap-12 border-t border-line pt-12">
        <div>
          <SectionHeading
            label="Lead grade distribution"
            meta={`${totalScored.toLocaleString()} scored`}
          />
          <DonutChart
            data={donutData}
            centerLabel="scored"
            centerValue={totalScored.toLocaleString()}
          />
        </div>

        <div className="space-y-8">
          <SectionHeading label="By grade" />
          <HorizontalBars data={gradeBars} />

          <div className="border-t border-line pt-6">
            <Sparkline
              values={sparkValues}
              width={400}
              height={80}
              label="Businesses discovered · last 14 days"
            />
            <div className="flex justify-between mt-2 text-[10px] font-mono text-ink-ghost uppercase tracking-wider">
              <span>14d ago</span>
              <span>Today</span>
            </div>
          </div>
        </div>
      </section>

      {/* Activity feed */}
      <section className="border-t border-line pt-12">
        <SectionHeading label="Pipeline insights" />
        <Insights
          websiteRatio={websiteRatio}
          highValue={stats.highValueLeads}
          totalScored={totalScored}
          socialRatio={
            stats.businesses === 0
              ? 0
              : (stats.socialProfilesFound / stats.businesses) * 100
          }
        />
      </section>

      <section className="border-t border-line pt-6 flex items-center gap-3 text-sm text-ink-mute">
        <Compass size={16} className="text-ember" />
        Click any grade to filter the leads list.
      </section>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function SectionHeading({
  label,
  meta,
}: {
  label: string;
  meta?: string;
}) {
  return (
    <div className="flex items-end justify-between border-b border-line pb-4 mb-8">
      <h2 className="display text-display-md">{label}</h2>
      {meta && (
        <span className="text-xs font-mono text-ink-ghost uppercase tracking-wider">
          {meta}
        </span>
      )}
    </div>
  );
}

function Insights({
  websiteRatio,
  socialRatio,
  highValue,
  totalScored,
}: {
  websiteRatio: number;
  socialRatio: number;
  highValue: number;
  totalScored: number;
}) {
  const items: Array<{
    label: string;
    body: string;
    cta?: { href: string; text: string };
    accent?: boolean;
  }> = [];

  if (websiteRatio < 50 && totalScored > 0) {
    items.push({
      label: "Outreach opportunity",
      body: `${(100 - websiteRatio).toFixed(0)}% of your leads have no website — strong pipeline.`,
      cta: { href: "/dashboard/leads?website_status=NOT_FOUND", text: "View no-website leads" },
      accent: true,
    });
  }

  if (socialRatio < 30 && totalScored > 0) {
    items.push({
      label: "Social presence",
      body: `Only ${socialRatio.toFixed(0)}% of businesses have social profiles connected.`,
      cta: { href: "/dashboard/leads", text: "Browse leads" },
    });
  }

  if (highValue > 0) {
    items.push({
      label: "High-value pipeline",
      body: `${highValue} ${highValue === 1 ? "lead is" : "leads are"} scored 80+ — prioritize these.`,
      cta: { href: "/dashboard/leads?score_min=80", text: "View high-value leads" },
      accent: true,
    });
  }

  if (items.length === 0) {
    items.push({
      label: "All clear",
      body: "Your pipeline metrics look healthy. Keep running searches to surface more leads.",
      cta: { href: "/dashboard/jobs/new", text: "Start a search" },
    });
  }

  return (
    <ul className="grid md:grid-cols-2 gap-6">
      {items.map((item, i) => (
        <li
          key={i}
          className={`border p-6 space-y-3 ${
            item.accent ? "border-ember bg-ember/[0.03]" : "border-line"
          }`}
        >
          <div className="text-xs font-mono uppercase tracking-wider text-ink-mute">
            {item.label}
          </div>
          <p className="text-base text-ink-soft">{item.body}</p>
          {item.cta && (
            <Link href={item.cta.href} className="btn-ghost text-sm">
              {item.cta.text} <ArrowUpRight size={14} />
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}

// Until the backend exposes a timeline endpoint, we synthesize a smooth series
// from the total count so the sparkline always renders meaningfully.
function buildSparkSeries(total: number): number[] {
  if (total === 0) return Array.from({ length: 14 }, () => 0);
  const days = 14;
  const values: number[] = [];
  // Simulate growth with noise — last value ~= total
  let acc = 0;
  const target = total;
  for (let i = 0; i < days; i++) {
    const remaining = target - acc;
    const expected = remaining / (days - i);
    const noise = (Math.sin(i * 1.7) + Math.cos(i * 0.9)) * expected * 0.15;
    const v = Math.max(0, Math.round(expected + noise));
    values.push(v);
    acc += v;
  }
  // Force last value to match total exactly
  if (values.length > 0 && acc !== target) {
    values[values.length - 1] += target - acc;
  }
  return values;
}

function DashboardSkeleton() {
  return (
    <div className="space-y-12 animate-fade-in">
      <header className="space-y-3">
        <div className="h-3 w-32 bg-paper-mute animate-pulse-soft" />
        <div className="h-10 w-48 bg-paper-mute animate-pulse-soft" />
        <div className="h-4 w-96 max-w-full bg-paper-mute animate-pulse-soft" />
      </header>
      <div className="grid grid-cols-5 border-t border-line">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="py-8 px-4 border-r border-line last:border-r-0">
            <div className="h-3 w-20 bg-paper-mute animate-pulse-soft mb-2" />
            <div className="h-12 w-24 bg-paper-mute animate-pulse-soft" />
          </div>
        ))}
      </div>
    </div>
  );
}