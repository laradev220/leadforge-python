"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowUpRight,
  ExternalLink,
  Loader2,
  Mail,
  Phone,
  RefreshCw,
  ShieldCheck,
  Star,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Lead } from "@/lib/types";
import {
  CONTACT_TYPE_LABELS,
  SOCIAL_PLATFORM_LABELS,
  WEBSITE_STATUS_LABELS,
  formatAddress,
  formatCount,
  formatLocation,
  formatRating,
  isValidUuid,
} from "@/lib/format";
import { formatRelative } from "@/lib/utils";
import { ScoreBreakdown } from "@/components/score-breakdown";
import { VerificationBadge } from "@/components/verification-badge";

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id ?? "";

  const [lead, setLead] = useState<Lead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    if (!isValidUuid(id)) {
      toast.error("Invalid lead ID");
      router.replace("/dashboard/leads");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getLead(id)
      .then((res) => {
        if (cancelled) return;
        setLead(res.data);
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
  }, [id, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={20} className="animate-spin text-ink-mute" />
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="py-20 text-center">
        <p className="display text-display-md mb-3">Not found</p>
        <p className="text-ink-mute text-sm mb-8">
          {error ?? "Lead not scored yet"}
        </p>
        <Link href="/dashboard/leads" className="btn-outline">
          Back to leads
        </Link>
      </div>
    );
  }

  const {
    business,
    lead_score,
    contacts,
    social_profiles,
    website,
    provenance = [],
  } = lead;
  const verifiable = contacts.filter(
    (c) => c.type === "EMAIL" || c.type === "PHONE",
  );

  async function reVerify() {
    setVerifying(true);
    try {
      await api.verifyBusiness(business.id, true);
      toast.success("Verification queued");
      setTimeout(() => {
        api
          .getLead(business.id)
          .then((res) => setLead(res.data))
          .catch(() => undefined);
      }, 5000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  }
  const topContacts = [...contacts]
    .sort((a, b) => b.confidence_score - a.confidence_score)
    .slice(0, 3);

  return (
    <div className="space-y-12 animate-fade-up">
      <header className="space-y-6">
        <Link
          href="/dashboard/leads"
          className="inline-block text-xs font-mono text-ink-mute uppercase tracking-wider hover:text-ember transition-colors"
        >
          ← All leads
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 max-w-2xl">
            <p className="status text-ink-mute mb-3">
              <span className="status-dot bg-ember" />
              {lead_score?.grade ?? "ungraded"} ·{" "}
              {WEBSITE_STATUS_LABELS[business.website_status].toLowerCase()}{" "}
              website
            </p>
            <h1 className="display text-display-lg text-balance">
              {business.name}
            </h1>
            {business.category && (
              <p className="text-ink-soft mt-2">
                {business.category} · {formatLocation(business)}
              </p>
            )}
          </div>

          <Link
            href={`/dashboard/businesses/${business.id}`}
            className="btn-outline"
          >
            Full business profile <ArrowUpRight size={14} />
          </Link>
        </div>
      </header>

      {/* Score section */}
      <section>
        <SectionHeading
          label="Outreach score"
          meta={
            lead_score
              ? `Calculated ${formatRelative(lead_score.calculated_at)}`
              : undefined
          }
        />
        <ScoreBreakdown score={lead_score} />
      </section>

      {/* Best contact action panel */}
      {lead_score?.best_contact_method && (
        <section className="border-y border-line py-8">
          <SectionHeading label="Recommended next step" />
          <BestContactAction
            method={lead_score.best_contact_method}
            contacts={topContacts}
          />
        </section>
      )}

      {/* Contact + reputation */}
      <section className="grid lg:grid-cols-2 gap-12">
        <Block label="Contacts found">
          {contacts.length === 0 ? (
            <Empty>No verified contacts yet</Empty>
          ) : (
            <ul className="space-y-3">
              {topContacts.map((c) => (
                <li key={c.id} className="flex items-start gap-3">
                  <span className="mt-0.5">
                    {c.type === "EMAIL" ? (
                      <Mail size={14} className="text-ink-mute" />
                    ) : (
                      <Phone size={14} className="text-ink-mute" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <a
                      href={
                        c.type === "EMAIL" ? `mailto:${c.value}` : `tel:${c.value}`
                      }
                      className="font-mono text-sm hover:text-ember transition-colors break-all"
                    >
                      {c.value}
                    </a>
                    <div className="text-xs text-ink-ghost font-mono mt-0.5">
                      {CONTACT_TYPE_LABELS[c.type]} ·{" "}
                      {Math.round(c.confidence_score)}% confidence
                    </div>
                  </div>
                </li>
              ))}
              {contacts.length > topContacts.length && (
                <li className="text-xs text-ink-mute font-mono">
                  +{contacts.length - topContacts.length} more
                </li>
              )}
            </ul>
          )}
        </Block>

        <Block label="Reputation">
          <div className="flex items-baseline gap-3">
            <span className="display text-5xl">
              {formatRating(business.rating)}
            </span>
            <span className="flex items-center gap-1 text-ember">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star
                  key={i}
                  size={14}
                  fill={
                    business.rating !== null && i < Math.round(business.rating)
                      ? "currentColor"
                      : "none"
                  }
                />
              ))}
            </span>
          </div>
          <p className="text-sm text-ink-mute mt-1">
            {formatCount(business.review_count)} reviews
          </p>
        </Block>
      </section>

      {/* Social + website */}
      <section className="grid lg:grid-cols-2 gap-12">
        <Block label="Social presence">
          {social_profiles.length === 0 ? (
            <Empty>No social profiles</Empty>
          ) : (
            <ul className="space-y-2">
              {social_profiles.map((s) => (
                <li key={s.id} className="flex items-center gap-3">
                  <span className="font-mono text-xs text-ink-mute w-24 uppercase tracking-wider">
                    {SOCIAL_PLATFORM_LABELS[s.platform]}
                  </span>
                  <a
                    href={s.profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm hover:text-ember transition-colors truncate flex items-center gap-1"
                  >
                    {s.username ?? s.profile_url}
                    <ExternalLink size={12} />
                  </a>
                  {s.followers !== null && (
                    <span className="ml-auto text-xs text-ink-ghost font-mono">
                      {formatCount(s.followers)} followers
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Block>

        <Block label="Website">
          {website ? (
            <>
              <a
                href={website.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-lg hover:text-ember transition-colors break-all"
              >
                {website.domain ?? website.url}
                <ExternalLink size={14} />
              </a>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <Stat
                  label="Reachable"
                  value={website.is_reachable ? "Yes" : "No"}
                />
                <Stat
                  label="SEO"
                  value={
                    website.seo_score !== null
                      ? `${website.seo_score}/100`
                      : "—"
                  }
                />
              </div>
            </>
          ) : (
            <Empty>No website — potential outreach opportunity</Empty>
          )}
        </Block>
      </section>

      <section className="border-t border-line pt-8">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <SectionHeading
            label="Contact verification"
            meta="MX, mailbox and phone-line checks"
          />
          <button
            type="button"
            onClick={reVerify}
            disabled={verifying}
            className="btn-outline inline-flex items-center gap-2"
          >
            {verifying ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            Re-verify
          </button>
        </div>
        {verifiable.length === 0 ? (
          <Empty>No email or phone contacts to verify</Empty>
        ) : (
          <ul className="divide-y divide-line border-y border-line">
            {verifiable.map((c) => {
              const v = c.verification;
              const checkedAt = v?.checked_at ? new Date(v.checked_at) : null;
              const stale =
                checkedAt !== null &&
                Date.now() - checkedAt.getTime() > 30 * 24 * 60 * 60 * 1000;
              return (
                <li
                  key={c.id}
                  className="flex flex-wrap items-center gap-3 py-3"
                >
                  <ShieldCheck size={14} className="text-ink-ghost" />
                  <span className="font-mono text-sm break-all">{c.value}</span>
                  <VerificationBadge verification={v} />
                  {v?.line_type && (
                    <span className="chip">{v.line_type.toLowerCase()}</span>
                  )}
                  {stale && <span className="chip text-amber-700">stale</span>}
                  <span className="ml-auto text-xs text-ink-ghost font-mono">
                    {v?.reason ?? "not checked"}
                    {v?.checked_at ? ` · ${formatRelative(v.checked_at)}` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-xs text-ink-mute mt-3">
          MX-only results are domain-checked; a configured SMTP/provider verifier
          upgrades them to mailbox-verified.
        </p>
      </section>

      {provenance.length > 0 && (
        <section>
          <SectionHeading
            label="Where this came from"
            meta={`${provenance.length} recorded fields`}
          />
          <div className="overflow-x-auto border-y border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase tracking-wider text-ink-mute">
                  <th className="py-2 pr-3">Field</th>
                  <th className="py-2 pr-3">Value</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">First seen</th>
                  <th className="py-2 pr-3">Last checked</th>
                  <th className="py-2">Conf.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {provenance.slice(0, 20).map((row) => (
                  <tr key={`${row.field}-${row.value}`}>
                    <td className="py-2 pr-3 font-mono text-xs text-ink-mute">
                      {row.field}
                    </td>
                    <td className="py-2 pr-3 max-w-[28ch] truncate" title={row.value}>
                      {row.value}
                    </td>
                    <td className="py-2 pr-3">
                      <span className="chip">{row.source}</span>
                    </td>
                    <td className="py-2 pr-3 text-xs text-ink-mute">
                      {formatRelative(row.first_seen_at)}
                    </td>
                    <td className="py-2 pr-3 text-xs text-ink-mute">
                      {formatRelative(row.last_checked_at)}
                    </td>
                    <td className="py-2 text-xs font-mono">{row.confidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="border-t border-line pt-6">
        <Block label="Address">
          <p className="text-base">{formatAddress(business) || "—"}</p>
        </Block>
      </section>
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function BestContactAction({
  method,
  contacts,
}: {
  method: string;
  contacts: Lead["contacts"];
}) {
  const matching = contacts.find(
    (c) =>
      c.type === method.toUpperCase().replace("EMAIL", "EMAIL").replace("PHONE", "PHONE"),
  );
  const fallback = contacts[0];
  const target = matching ?? fallback;

  return (
    <div className="flex flex-wrap items-center justify-between gap-6">
      <div>
        <p className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
          Best channel
        </p>
        <p className="display text-3xl capitalize">{method}</p>
      </div>
      {target && (
        <a
          href={
            target.type === "EMAIL" ? `mailto:${target.value}` : `tel:${target.value}`
          }
          className="btn-solid"
        >
          {target.type === "EMAIL" ? (
            <>
              <Mail size={14} /> Email now
            </>
          ) : (
            <>
              <Phone size={14} /> Call now
            </>
          )}
        </a>
      )}
    </div>
  );
}

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

function Block({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-mono uppercase tracking-wider text-ink-mute">
        {label}
      </h3>
      <div>{children}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-ink-ghost italic">{children}</p>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-ink-ghost uppercase tracking-wider font-mono">
        {label}
      </div>
      <div className="font-mono">{value}</div>
    </div>
  );
}