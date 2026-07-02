"use client";

import { useUrlFilters } from "@/lib/use-url-filters";
import {
  WEBSITE_STATUS_LABELS,
  type WebsiteStatus,
} from "@/lib/format";

type Filters = {
  name: string;
  city: string;
  country: string;
  category: string;
  website_status: string;
  min_rating: string;
  max_rating: string;
};

const DEFAULTS: Filters = {
  name: "",
  city: "",
  country: "",
  category: "",
  website_status: "",
  min_rating: "",
  max_rating: "",
};

const STATUS_OPTIONS: WebsiteStatus[] = [
  "FOUND",
  "NOT_FOUND",
  "INVALID",
  "UNKNOWN",
];

export function BusinessFilters({
  resultCount,
}: {
  resultCount?: number;
}) {
  const { values, setValues, reset } = useUrlFilters(DEFAULTS);

  const hasActive = Object.entries(values).some(
    ([key, v]) => v && key !== "name",
  );
  const hasName = !!values.name;

  return (
    <aside className="space-y-8 animate-fade-in">
      <div>
        <h2 className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-4">
          Filters
        </h2>
        {typeof resultCount === "number" && (
          <p className="text-xs text-ink-ghost font-mono">
            {resultCount.toLocaleString()} result{resultCount === 1 ? "" : "s"}
          </p>
        )}
      </div>

      <div className="space-y-5">
        <TextField
          label="Name"
          value={values.name ?? ""}
          onChange={(v) => setValues({ name: v })}
          placeholder="e.g. Joe's Pizza"
        />
        <TextField
          label="City"
          value={values.city ?? ""}
          onChange={(v) => setValues({ city: v })}
          placeholder="e.g. Houston"
        />
        <TextField
          label="Country"
          value={values.country ?? ""}
          onChange={(v) => setValues({ country: v.toUpperCase() })}
          placeholder="US"
          maxLength={2}
        />
        <TextField
          label="Category"
          value={values.category ?? ""}
          onChange={(v) => setValues({ category: v })}
          placeholder="e.g. Restaurant"
        />

        <div>
          <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
            Website status
          </label>
          <div className="space-y-1.5">
            <RadioRow
              checked={!values.website_status}
              onChange={() => setValues({ website_status: "" })}
              label="Any"
            />
            {STATUS_OPTIONS.map((s) => (
              <RadioRow
                key={s}
                checked={values.website_status === s}
                onChange={() => setValues({ website_status: s })}
                label={WEBSITE_STATUS_LABELS[s]}
              />
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
            Rating
          </label>
          <div className="grid grid-cols-2 gap-3">
            <NumberField
              value={values.min_rating ?? ""}
              onChange={(v) => setValues({ min_rating: v })}
              placeholder="Min"
              min={0}
              max={5}
              step={0.1}
            />
            <NumberField
              value={values.max_rating ?? ""}
              onChange={(v) => setValues({ max_rating: v })}
              placeholder="Max"
              min={0}
              max={5}
              step={0.1}
            />
          </div>
        </div>
      </div>

      {(hasActive || hasName) && (
        <button
          type="button"
          onClick={reset}
          className="text-xs font-mono uppercase tracking-wider text-ink-mute hover:text-ember transition-colors"
        >
          Clear all
        </button>
      )}
    </aside>
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
        className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm placeholder:text-ink-ghost focus:outline-none focus:border-ember transition-colors"
      />
    </div>
  );
}

function NumberField({
  value,
  onChange,
  placeholder,
  min,
  max,
  step,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      max={max}
      step={step}
      className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm placeholder:text-ink-ghost focus:outline-none focus:border-ember transition-colors"
    />
  );
}

function RadioRow({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      className="flex items-center gap-2.5 text-sm w-full text-left py-1 hover:text-ember transition-colors"
    >
      <span
        className={`h-3 w-3 rounded-full border ${
          checked ? "border-ember bg-ember" : "border-ink/40"
        } transition-colors`}
      />
      <span className={checked ? "text-ink" : "text-ink-mute"}>{label}</span>
    </button>
  );
}