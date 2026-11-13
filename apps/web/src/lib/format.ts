import type {
  Business,
  Contact,
  ContactType,
  ExportFormat,
  ExportStatus,
  LeadGrade,
  SearchJobStatus,
  SocialPlatform,
  WebsiteStatus,
} from "@/lib/types";

// Re-export enums for convenience
export type {
  ContactType,
  ExportFormat,
  ExportStatus,
  LeadGrade,
  SearchJobStatus,
  SocialPlatform,
  WebsiteStatus,
};

// ── Status helpers ─────────────────────────────────────────────────────────

export const SEARCH_JOB_STATUS_LABELS: Record<SearchJobStatus, string> = {
  PENDING: "Pending",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export const SEARCH_JOB_STATUS_COLORS: Record<SearchJobStatus, string> = {
  PENDING: "bg-ink-ghost",
  RUNNING: "bg-ember animate-pulse-soft",
  COMPLETED: "bg-moss",
  FAILED: "bg-red-700",
  CANCELLED: "bg-ink-ghost",
};

export const WEBSITE_STATUS_LABELS: Record<WebsiteStatus, string> = {
  UNKNOWN: "Unknown",
  FOUND: "Found",
  NOT_FOUND: "No website",
  INVALID: "Invalid",
};

export const WEBSITE_STATUS_COLORS: Record<WebsiteStatus, string> = {
  UNKNOWN: "bg-ink-ghost",
  FOUND: "bg-moss",
  NOT_FOUND: "bg-ember",
  INVALID: "bg-red-700",
};

// ── Exports ────────────────────────────────────────────────────────────────

export const EXPORT_FORMATS: ExportFormat[] = ["CSV", "XLSX", "JSON"];

export const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = {
  CSV: "CSV",
  XLSX: "XLSX",
  JSON: "JSON",
};

export const EXPORT_FORMAT_DESCRIPTIONS: Record<ExportFormat, string> = {
  CSV: "Comma-separated. Works in Excel, Google Sheets, Numbers.",
  XLSX: "Native Excel format. Preserves formatting on open.",
  JSON: "Structured data. Best for piping into other tools.",
};

export const EXPORT_STATUS_LABELS: Record<ExportStatus, string> = {
  PENDING: "Queued",
  PROCESSING: "Processing",
  COMPLETED: "Ready",
  FAILED: "Failed",
};

export const EXPORT_STATUS_COLORS: Record<ExportStatus, string> = {
  PENDING: "bg-ink-ghost",
  PROCESSING: "bg-ember animate-pulse-soft",
  COMPLETED: "bg-moss",
  FAILED: "bg-red-700",
};

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let value = bytes;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

// ── Lead grading ──────────────────────────────────────────────────────────

export const LEAD_GRADES: LeadGrade[] = ["A+", "A", "B", "C", "D", "F"];

// Map grade → text color (using inline classes for fine control over editorial palette)
export const LEAD_GRADE_TONE: Record<LeadGrade, string> = {
  "A+": "text-ember",
  A: "text-ember",
  B: "text-ink",
  C: "text-ink-soft",
  D: "text-ink-mute",
  F: "text-ink-ghost",
};

// Map grade → visual weight for emphasis
export function gradeWeight(grade: LeadGrade | null | undefined): "bold" | "normal" {
  if (!grade) return "normal";
  return grade === "A+" || grade === "A" ? "bold" : "normal";
}

// Score → grade (client-side preview, server is source of truth)
export function scoreToGrade(score: number): LeadGrade {
  if (score >= 90) return "A+";
  if (score >= 80) return "A";
  if (score >= 65) return "B";
  if (score >= 50) return "C";
  if (score >= 35) return "D";
  return "F";
}

export const CONTACT_TYPE_LABELS: Record<ContactType, string> = {
  EMAIL: "Email",
  PHONE: "Phone",
  WHATSAPP: "WhatsApp",
  CONTACT_FORM: "Contact form",
  FACEBOOK: "Facebook",
  INSTAGRAM: "Instagram",
  LINKEDIN: "LinkedIn",
  YOUTUBE: "YouTube",
  TIKTOK: "TikTok",
  TWITTER: "Twitter",
};

export const SOCIAL_PLATFORM_LABELS: Record<SocialPlatform, string> = {
  FACEBOOK: "Facebook",
  INSTAGRAM: "Instagram",
  LINKEDIN: "LinkedIn",
  YOUTUBE: "YouTube",
  TIKTOK: "TikTok",
  TWITTER: "Twitter / X",
};

export const SOCIAL_PLATFORM_DOMAINS: Record<SocialPlatform, string> = {
  FACEBOOK: "facebook.com",
  INSTAGRAM: "instagram.com",
  LINKEDIN: "linkedin.com",
  YOUTUBE: "youtube.com",
  TIKTOK: "tiktok.com",
  TWITTER: "x.com",
};

// ── Formatting helpers ─────────────────────────────────────────────────────

export function formatRating(rating: number | null | undefined): string {
  if (rating === null || rating === undefined) return "—";
  return rating.toFixed(1);
}

export function formatCount(count: number | null | undefined): string {
  if (count === null || count === undefined) return "—";
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`;
  return String(count);
}

export function formatLocation(b: Business): string {
  const parts = [b.city, b.state, b.country].filter(Boolean);
  return parts.join(", ") || "—";
}

export function formatAddress(b: Business): string {
  const parts = [b.address, b.city, b.state, b.postal_code, b.country].filter(
    Boolean,
  );
  return parts.join(", ");
}

// ── Sort/filter helpers ────────────────────────────────────────────────────

export const SORT_OPTIONS = [
  { value: "created_at:desc", label: "Newest first" },
  { value: "created_at:asc", label: "Oldest first" },
  { value: "name:asc", label: "Name A–Z" },
  { value: "name:desc", label: "Name Z–A" },
  { value: "rating:desc", label: "Highest rated" },
  { value: "rating:asc", label: "Lowest rated" },
  { value: "review_count:desc", label: "Most reviewed" },
] as const;

export const LEAD_SORT_OPTIONS = [
  { value: "score:desc", label: "Highest score" },
  { value: "score:asc", label: "Lowest score" },
  { value: "grade:asc", label: "Best grade" },
  { value: "created_at:desc", label: "Newest" },
  { value: "created_at:asc", label: "Oldest" },
  { value: "name:asc", label: "Name A–Z" },
] as const;

export type SortValue = string;

export function parseSort(value: string | null): SortValue {
  const found = SORT_OPTIONS.find((o) => o.value === value);
  return (found?.value ?? "created_at:desc") as SortValue;
}

export function parsePage(value: string | null): number {
  if (!value) return 1;
  const n = parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

export function parseRating(value: string | null): number | undefined {
  if (!value) return undefined;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

// ── Validation helpers ─────────────────────────────────────────────────────

export function isValidUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
    value,
  );
}

// ── Grouping helpers ───────────────────────────────────────────────────────

export function groupContactsByType(contacts: Contact[]): Record<ContactType, Contact[]> {
  const result: Partial<Record<ContactType, Contact[]>> = {};
  for (const c of contacts) {
    if (!result[c.type]) result[c.type] = [];
    result[c.type]!.push(c);
  }
  return result as Record<ContactType, Contact[]>;
}