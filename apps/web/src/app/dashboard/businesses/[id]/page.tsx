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
  Plus,
  RefreshCw,
  Star,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Business,
  Contact,
  ContactType,
  SocialProfile,
  Website,
} from "@/lib/types";
import {
  CONTACT_TYPE_LABELS,
  SOCIAL_PLATFORM_DOMAINS,
  SOCIAL_PLATFORM_LABELS,
  WEBSITE_STATUS_COLORS,
  WEBSITE_STATUS_LABELS,
  formatAddress,
  formatCount,
  formatLocation,
  formatRating,
  isValidUuid,
} from "@/lib/format";

type Tab = "overview" | "website" | "contacts" | "socials";

export default function BusinessDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id ?? "";

  const [business, setBusiness] = useState<Business | null>(null);
  const [website, setWebsite] = useState<Website | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [socials, setSocials] = useState<SocialProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [reEnriching, setReEnriching] = useState(false);

  // Validate ID format
  useEffect(() => {
    if (!isValidUuid(id)) {
      toast.error("Invalid business ID");
      router.replace("/dashboard/businesses");
    }
  }, [id, router]);

  useEffect(() => {
    if (!isValidUuid(id)) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      api.getBusiness(id),
      api.getBusinessWebsite(id).catch(() => ({ success: true, data: null })),
      api.listBusinessContacts(id).catch(() => ({ success: true, data: [] })),
      api.listBusinessSocialProfiles(id).catch(() => ({ success: true, data: [] })),
    ])
      .then(([b, w, c, s]) => {
        if (cancelled) return;
        setBusiness(b.data);
        setWebsite(w.data);
        setContacts(c.data);
        setSocials(s.data);
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
  }, [id]);

  async function handleReEnrich() {
    if (!business) return;
    setReEnriching(true);
    try {
      await api.reEnrichBusiness(business.id);
      toast.success("Re-enrichment queued");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setReEnriching(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={20} className="animate-spin text-ink-mute" />
      </div>
    );
  }

  if (error || !business) {
    return (
      <div className="py-20 text-center">
        <p className="display text-display-md mb-3">Not found</p>
        <p className="text-ink-mute text-sm mb-8">{error ?? "Business doesn't exist"}</p>
        <Link href="/dashboard/businesses" className="btn-outline">
          Back to businesses
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-12 animate-fade-up">
      <header className="space-y-6">
        <Link
          href="/dashboard/businesses"
          className="inline-block text-xs font-mono text-ink-mute uppercase tracking-wider hover:text-ember transition-colors"
        >
          ← All businesses
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <p className="status text-ink-mute mb-3">
              <span
                className={`status-dot ${WEBSITE_STATUS_COLORS[business.website_status]}`}
              />
              {WEBSITE_STATUS_LABELS[business.website_status].toLowerCase()} website
              {business.source ? ` · from ${business.source.toLowerCase().replace("_", " ")}` : ""}
            </p>
            <h1 className="display text-display-lg text-balance max-w-[24ch]">
              {business.name}
            </h1>
            {business.category && (
              <p className="text-ink-soft mt-2">
                {business.category}
                {formatLocation(business) !== "—"
                  ? ` · ${formatLocation(business)}`
                  : ""}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={handleReEnrich}
            disabled={reEnriching}
            className="btn-outline"
          >
            {reEnriching ? (
              <>
                <Loader2 size={14} className="animate-spin" /> Re-enriching…
              </>
            ) : (
              <>
                <RefreshCw size={14} /> Re-enrich
              </>
            )}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-line -mb-px overflow-x-auto">
          {(
            [
              { key: "overview", label: "Overview" },
              { key: "website", label: "Website", count: website ? 1 : 0 },
              { key: "contacts", label: "Contacts", count: contacts.length },
              { key: "socials", label: "Socials", count: socials.length },
            ] as Array<{ key: Tab; label: string; count?: number }>
          ).map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors ${
                activeTab === t.key
                  ? "border-ink text-ink"
                  : "border-transparent text-ink-mute hover:text-ink"
              }`}
            >
              {t.label}
              {typeof t.count === "number" && t.count > 0 && (
                <span className="ml-2 text-xs font-mono text-ink-ghost">
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </header>

      <section>
        {activeTab === "overview" && (
          <OverviewPanel
            business={business}
            website={website}
            contacts={contacts}
            socials={socials}
          />
        )}
        {activeTab === "website" && <WebsitePanel website={website} />}
        {activeTab === "contacts" && (
          <ContactsPanel
            businessId={business.id}
            contacts={contacts}
            onAdd={(c) => setContacts((prev) => [...prev, c])}
          />
        )}
        {activeTab === "socials" && <SocialsPanel socials={socials} />}
      </section>
    </div>
  );
}

// ── Panels ─────────────────────────────────────────────────────────────────

function OverviewPanel({
  business,
  website,
  contacts,
  socials,
}: {
  business: Business;
  website: Website | null;
  contacts: Contact[];
  socials: SocialProfile[];
}) {
  return (
    <div className="grid lg:grid-cols-2 gap-12">
      <Block label="Location">
        {formatAddress(business) === "" ? (
          <Empty>No address on record</Empty>
        ) : (
          <p className="text-lg">{formatAddress(business)}</p>
        )}
        {business.latitude !== null && business.longitude !== null && (
          <p className="text-xs text-ink-mute font-mono mt-2">
            {business.latitude.toFixed(4)}, {business.longitude.toFixed(4)}
          </p>
        )}
      </Block>

      <Block label="Reputation">
        <div className="flex items-baseline gap-3">
          <span className="display text-5xl">{formatRating(business.rating)}</span>
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

      <Block label="Contact">
        {contacts.length === 0 ? (
          <Empty>No contacts yet — workers are still enriching</Empty>
        ) : (
          <ul className="space-y-2">
            {contacts.slice(0, 5).map((c) => (
              <li key={c.id} className="flex items-center gap-3">
                {c.type === "EMAIL" ? (
                  <Mail size={14} className="text-ink-mute" />
                ) : (
                  <Phone size={14} className="text-ink-mute" />
                )}
                <span className="font-mono text-sm">{c.value}</span>
                <span className="text-xs text-ink-ghost ml-auto">
                  {CONTACT_TYPE_LABELS[c.type]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block label="Website">
        {website ? (
          <a
            href={website.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-lg hover:text-ember transition-colors break-all"
          >
            {website.domain ?? website.url}
            <ExternalLink size={14} />
          </a>
        ) : (
          <Empty>This business has no website on record</Empty>
        )}
      </Block>

      <Block label="Social presence">
        {socials.length === 0 ? (
          <Empty>No social profiles discovered</Empty>
        ) : (
          <ul className="space-y-2">
            {socials.slice(0, 5).map((s) => (
              <li key={s.id} className="flex items-center gap-3">
                <span className="font-mono text-xs text-ink-mute w-20 uppercase tracking-wider">
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
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block label="External IDs">
        <p className="font-mono text-sm break-all">
          {business.external_id ?? "—"}
        </p>
        <p className="text-xs text-ink-mute mt-2">
          Claimed: {business.is_claimed === null ? "—" : business.is_claimed ? "Yes" : "No"}
        </p>
      </Block>
    </div>
  );
}

function WebsitePanel({ website }: { website: Website | null }) {
  if (!website) {
    return (
      <div className="py-16 text-center border-y border-line">
        <p className="display text-display-md mb-3">No website</p>
        <p className="text-ink-mute text-sm max-w-md mx-auto">
          We didn't find a website for this business. Could be an opportunity
          for outreach.
        </p>
      </div>
    );
  }
  return (
    <div className="grid lg:grid-cols-2 gap-12">
      <Block label="URL">
        <a
          href={website.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-lg hover:text-ember break-all"
        >
          {website.url}
          <ExternalLink size={14} />
        </a>
      </Block>
      <Block label="Status">
        <Stat label="Reachable" value={website.is_reachable ? "Yes" : "No"} />
        <Stat label="SSL" value={website.ssl_enabled ? "Enabled" : "Disabled"} />
        <Stat
          label="HTTP"
          value={website.http_status !== null ? String(website.http_status) : "—"}
        />
        <Stat
          label="Load"
          value={
            website.load_time_ms !== null
              ? `${website.load_time_ms.toLocaleString()}ms`
              : "—"
          }
        />
      </Block>
      <Block label="Mobile & SEO">
        <Stat label="Mobile friendly" value={website.mobile_friendly ? "Yes" : "No"} />
        <Stat
          label="SEO score"
          value={website.seo_score !== null ? `${website.seo_score}/100` : "—"}
        />
      </Block>
    </div>
  );
}

function ContactsPanel({
  businessId,
  contacts,
  onAdd,
}: {
  businessId: string;
  contacts: Contact[];
  onAdd: (c: Contact) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [type, setType] = useState<ContactType>("EMAIL");
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.addBusinessContact(businessId, type, value.trim());
      onAdd(res.data);
      setValue("");
      setShowForm(false);
      toast.success("Contact added");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-mute">
          {contacts.length} contact{contacts.length === 1 ? "" : "s"} extracted
        </p>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="btn-ghost text-sm"
        >
          {showForm ? "Cancel" : (
            <>
              <Plus size={14} /> Add manual contact
            </>
          )}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleAdd}
          className="grid grid-cols-1 md:grid-cols-[180px_1fr_auto] gap-4 border-y border-line py-6 animate-fade-in"
        >
          <select
            value={type}
            onChange={(e) => setType(e.target.value as ContactType)}
            className="bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
          >
            {Object.entries(CONTACT_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={type === "EMAIL" ? "name@company.com" : "+1 555 0123"}
            className="bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
          />
          <button type="submit" disabled={submitting} className="btn-solid">
            {submitting ? "Saving…" : "Save"}
          </button>
        </form>
      )}

      {contacts.length === 0 ? (
        <div className="py-16 text-center border-y border-line">
          <p className="display text-display-md mb-3">No contacts</p>
          <p className="text-ink-mute text-sm">Add one manually or wait for workers to enrich.</p>
        </div>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {contacts.map((c) => (
            <li
              key={c.id}
              className="grid grid-cols-12 gap-4 items-center py-4 px-2"
            >
              <span className="col-span-3 text-xs font-mono uppercase tracking-wider text-ink-mute">
                {CONTACT_TYPE_LABELS[c.type]}
              </span>
              <span className="col-span-5 font-mono text-sm break-all">
                {c.value}
              </span>
              <span className="col-span-2 text-xs text-ink-mute font-mono uppercase tracking-wider">
                {c.source.toLowerCase()}
              </span>
              <span className="col-span-2 text-right text-xs text-ink-mute">
                {c.confidence_score}% conf
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SocialsPanel({ socials }: { socials: SocialProfile[] }) {
  if (socials.length === 0) {
    return (
      <div className="py-16 text-center border-y border-line">
        <p className="display text-display-md mb-3">No social profiles</p>
        <p className="text-ink-mute text-sm">
          Workers haven't found any social presence yet.
        </p>
      </div>
    );
  }
  return (
    <ul className="grid md:grid-cols-2 gap-4">
      {socials.map((s) => (
        <li key={s.id} className="border border-line p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-display text-xl">{SOCIAL_PLATFORM_LABELS[s.platform]}</span>
            <a
              href={s.profile_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-ink-mute hover:text-ember transition-colors"
            >
              <ArrowUpRight size={16} />
            </a>
          </div>
          {s.username && (
            <p className="text-xs text-ink-mute font-mono">@{s.username}</p>
          )}
          {s.bio && (
            <p className="text-sm text-ink-soft line-clamp-3">{s.bio}</p>
          )}
          <div className="grid grid-cols-3 gap-3 pt-2 border-t border-line text-xs">
            <Stat label="Followers" value={formatCount(s.followers)} inline />
            <Stat label="Following" value={formatCount(s.following)} inline />
            <Stat label="Posts" value={formatCount(s.posts_count)} inline />
          </div>
          {(s.public_email || s.public_phone || s.website) && (
            <div className="border-t border-line pt-3 space-y-1 text-xs">
              {s.public_email && (
                <p className="text-ink-mute font-mono">{s.public_email}</p>
              )}
              {s.public_phone && (
                <p className="text-ink-mute font-mono">{s.public_phone}</p>
              )}
              {s.website && (
                <a
                  href={s.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink-mute hover:text-ember transition-colors flex items-center gap-1"
                >
                  {SOCIAL_PLATFORM_DOMAINS[s.platform] === new URL(s.website).hostname.replace("www.", "")
                    ? s.website
                    : s.website}
                  <ExternalLink size={10} />
                </a>
              )}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

// ── Shared building blocks ─────────────────────────────────────────────────

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

function Stat({
  label,
  value,
  inline = false,
}: {
  label: string;
  value: string;
  inline?: boolean;
}) {
  if (inline) {
    return (
      <div>
        <div className="text-ink-ghost uppercase tracking-wider font-mono text-[10px]">
          {label}
        </div>
        <div className="text-sm">{value}</div>
      </div>
    );
  }
  return (
    <div className="flex justify-between text-sm py-1">
      <span className="text-ink-mute">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}