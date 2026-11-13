"use client";

import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { X, Loader2, FileText } from "lucide-react";
import { api } from "@/lib/api";
import type {
  ExportFilters,
  ExportFormat,
  ExportRecord,
  LeadGrade,
  WebsiteStatus,
  ContactType,
} from "@/lib/types";
import {
  EXPORT_FORMATS,
  EXPORT_FORMAT_DESCRIPTIONS,
  EXPORT_FORMAT_LABELS,
  LEAD_GRADES,
  WEBSITE_STATUS_LABELS,
  CONTACT_TYPE_LABELS,
} from "@/lib/format";

export function CreateExportModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (record: { export_id: string }) => void;
}) {
  const [format, setFormat] = useState<ExportFormat>("CSV");
  const [grade, setGrade] = useState<LeadGrade | "">("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [bestContactMethod, setBestContactMethod] = useState<ContactType | "">("");
  const [websiteStatus, setWebsiteStatus] = useState<WebsiteStatus | "">("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Close on escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function reset() {
    setFormat("CSV");
    setGrade("");
    setMinScore("");
    setMaxScore("");
    setBestContactMethod("");
    setWebsiteStatus("");
    setCity("");
    setCountry("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const filters: ExportFilters = {};
      if (grade) filters.grade = grade as LeadGrade;
      const parsedMin = parseFloat(minScore);
      const parsedMax = parseFloat(maxScore);
      if (
        Number.isFinite(parsedMin) &&
        Number.isFinite(parsedMax) &&
        parsedMin > parsedMax
      ) {
        toast.error("Min score cannot be greater than max score");
        return;
      }
      if (Number.isFinite(parsedMin)) filters.score_min = parsedMin;
      if (Number.isFinite(parsedMax)) filters.score_max = parsedMax;
      if (bestContactMethod) filters.best_contact_method = bestContactMethod as ContactType;
      if (websiteStatus) filters.website_status = websiteStatus as WebsiteStatus;
      if (city.trim()) filters.city = city.trim();
      if (country.trim()) filters.country = country.trim().toUpperCase();

      const payload: { format: ExportFormat; filters: ExportFilters } = {
        format,
        filters,
      };
      const res = await api.createExport(payload);
      toast.success("Export queued");
      reset();
      onCreated(res.data);
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create export");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
    >
      <div
        className="absolute inset-0 bg-ink/40"
        onClick={onClose}
        aria-hidden
      />
      <div className="relative w-full max-w-xl bg-paper border border-line max-h-[90vh] overflow-y-auto">
        <header className="flex items-center justify-between px-6 py-4 border-b border-line sticky top-0 bg-paper">
          <h2 id="export-modal-title" className="display text-xl">
            New export
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-ink-mute hover:text-ember transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </header>

        <form onSubmit={onSubmit} className="px-6 py-6 space-y-8">
          {/* Format */}
          <fieldset>
            <legend className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-3">
              Format
            </legend>
            <div className="space-y-2">
              {EXPORT_FORMATS.map((f) => (
                <FormatOption
                  key={f}
                  value={f}
                  selected={format === f}
                  onSelect={() => setFormat(f)}
                  label={EXPORT_FORMAT_LABELS[f]}
                  description={EXPORT_FORMAT_DESCRIPTIONS[f]}
                />
              ))}
            </div>
          </fieldset>

          {/* Filters */}
          <fieldset className="space-y-5 border-t border-line pt-6">
            <legend className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-3">
              Filters (optional)
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <SelectField
                label="Min grade"
                value={grade}
                onChange={(v) => setGrade(v as LeadGrade | "")}
                options={[
                  { value: "", label: "Any" },
                  ...LEAD_GRADES.map((g) => ({ value: g, label: g })),
                ]}
              />
              <SelectField
                label="Best channel"
                value={bestContactMethod}
                onChange={(v) => setBestContactMethod(v as ContactType | "")}
                options={[
                  { value: "", label: "Any" },
                  ...Object.entries(CONTACT_TYPE_LABELS).map(([k, v]) => ({
                    value: k,
                    label: v,
                  })),
                ]}
              />
              <NumberField
                label="Min score"
                value={minScore}
                onChange={setMinScore}
                placeholder="0"
                min={0}
                max={100}
              />
              <NumberField
                label="Max score"
                value={maxScore}
                onChange={setMaxScore}
                placeholder="100"
                min={0}
                max={100}
              />
              <SelectField
                label="Website"
                value={websiteStatus}
                onChange={(v) => setWebsiteStatus(v as WebsiteStatus | "")}
                options={[
                  { value: "", label: "Any" },
                  ...Object.entries(WEBSITE_STATUS_LABELS).map(([k, v]) => ({
                    value: k,
                    label: v,
                  })),
                ]}
              />
              <div className="grid grid-cols-2 gap-2 col-span-1">
                <TextField
                  label="City"
                  value={city}
                  onChange={setCity}
                  placeholder="Any"
                />
                <TextField
                  label="Country"
                  value={country}
                  onChange={(v) => setCountry(v.toUpperCase())}
                  placeholder="US"
                  maxLength={2}
                />
              </div>
            </div>
          </fieldset>

          <div className="flex items-center justify-end gap-3 border-t border-line pt-6">
            <button
              type="button"
              onClick={onClose}
              className="btn-ghost"
              disabled={submitting}
            >
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn-solid">
              {submitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Creating…
                </>
              ) : (
                <>
                  <FileText size={14} /> Create export
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Form atoms ─────────────────────────────────────────────────────────────

function FormatOption({
  value,
  selected,
  onSelect,
  label,
  description,
}: {
  value: ExportFormat;
  selected: boolean;
  onSelect: () => void;
  label: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left border px-4 py-3 transition-colors ${
        selected
          ? "border-ember bg-ember/[0.04]"
          : "border-line hover:border-ink/40"
      }`}
    >
      <div className="flex items-center gap-3">
        <span
          className={`h-3 w-3 rounded-full border ${
            selected ? "border-ember bg-ember" : "border-ink/40"
          } transition-colors`}
        />
        <span className="font-display text-base">{label}</span>
      </div>
      <p className="text-xs text-ink-mute mt-1.5 ml-6">{description}</p>
    </button>
  );
}

function SelectField({
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

function NumberField({
  label,
  value,
  onChange,
  placeholder,
  min,
  max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
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
        placeholder={placeholder}
        min={min}
        max={max}
        className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm placeholder:text-ink-ghost focus:outline-none focus:border-ember transition-colors"
      />
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
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
        placeholder={placeholder}
        maxLength={maxLength}
        className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm placeholder:text-ink-ghost focus:outline-none focus:border-ember transition-colors uppercase"
      />
    </div>
  );
}