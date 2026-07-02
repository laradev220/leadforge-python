"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ArrowUpRight } from "lucide-react";

const SUGGESTIONS = [
  { keyword: "Dentist", location: "Houston", country: "US" },
  { keyword: "Plumber", location: "Brooklyn", country: "US" },
  { keyword: "Restaurant", location: "London", country: "GB" },
  { keyword: "Law firm", location: "Lahore", country: "PK" },
];

export default function NewJobPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    keyword: "",
    location: "",
    country: "",
    radius_km: "",
  });
  const [loading, setLoading] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function applySuggestion(s: (typeof SUGGESTIONS)[number]) {
    setForm({
      keyword: s.keyword,
      location: s.location,
      country: s.country,
      radius_km: "",
    });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.keyword || !form.location) return;
    setLoading(true);
    try {
      const res = await api.createSearchJob({
        keyword: form.keyword,
        location: form.location,
        country: form.country || undefined,
        radius_km: form.radius_km ? Number(form.radius_km) : undefined,
      });
      toast.success("Job queued");
      router.push(`/dashboard/jobs`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-12 animate-fade-up">
      <header>
        <Link href="/dashboard/jobs" className="text-xs font-mono text-ink-mute uppercase tracking-wider hover:text-ember transition-colors">
          ← All jobs
        </Link>
        <h1 className="display text-display-lg mt-6 text-balance max-w-[18ch]">
          Start a new discovery.
        </h1>
        <p className="text-ink-mute mt-3 max-w-md">
          Be specific. Workers enrich whatever they find — clearer inputs mean
          better results.
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-10 border-t border-line pt-10">
        <div className="grid md:grid-cols-2 gap-x-10 gap-y-8">
          <Field
            label="What are you looking for?"
            hint='e.g. "Dentist", "Plumber", "Restaurant"'
          >
            <input
              required
              value={form.keyword}
              onChange={(e) => update("keyword", e.target.value)}
              className="field"
              placeholder="Dentist"
            />
          </Field>

          <Field
            label="Where?"
            hint='City, neighborhood, or region'
          >
            <input
              required
              value={form.location}
              onChange={(e) => update("location", e.target.value)}
              className="field"
              placeholder="Houston, TX"
            />
          </Field>

          <Field label="Country (ISO code)" hint="Optional but improves accuracy">
            <input
              maxLength={2}
              value={form.country}
              onChange={(e) => update("country", e.target.value.toUpperCase())}
              className="field uppercase"
              placeholder="US"
            />
          </Field>

          <Field label="Radius (km)" hint="Leave empty for default">
            <input
              type="number"
              min={1}
              max={200}
              value={form.radius_km}
              onChange={(e) => update("radius_km", e.target.value)}
              className="field"
              placeholder="25"
            />
          </Field>
        </div>

        <div className="flex items-center gap-4">
          <button type="submit" disabled={loading} className="btn-solid">
            {loading ? "Queueing…" : "Run search"}
            {!loading && <ArrowUpRight size={16} />}
          </button>
          <Link href="/dashboard/jobs" className="btn-ghost">Cancel</Link>
        </div>
      </form>

      <section className="border-t border-line pt-10">
        <h2 className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-4">
          Quick start
        </h2>
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              type="button"
              key={s.keyword + s.location}
              onClick={() => applySuggestion(s)}
              className="text-left border border-line px-4 py-3 hover:border-ember hover:text-ember transition-colors"
            >
              <div className="font-display text-base">{s.keyword}</div>
              <div className="text-xs text-ink-mute">{s.location}, {s.country}</div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-1">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-ink-ghost mt-1">{hint}</p>}
    </div>
  );
}