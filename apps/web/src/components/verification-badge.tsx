import type { ContactVerification, PhoneLineType } from "@/lib/types";

const VERIFICATION_STYLES: Record<string, { label: string; className: string }> = {
  VALID: { label: "✓ verified", className: "text-emerald-800 bg-emerald-50 border-emerald-200" },
  RISKY: { label: "domain-checked", className: "text-amber-800 bg-amber-50 border-amber-200" },
  CATCH_ALL: { label: "catch-all", className: "text-amber-800 bg-amber-50 border-amber-200" },
  INVALID: { label: "invalid", className: "text-red-800 bg-red-50 border-red-200" },
  UNKNOWN: { label: "unknown", className: "text-ink-mute bg-ink/5 border-line" },
};

export function VerificationBadge({
  verification,
}: {
  verification?: ContactVerification | null;
}) {
  if (!verification || verification.status === "UNVERIFIED") return null;
  const style = VERIFICATION_STYLES[verification.status] ?? VERIFICATION_STYLES.UNKNOWN;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider ${style.className}`}
      title={verification.reason ?? undefined}
    >
      {style.label}
    </span>
  );
}

export function PhoneTypeBadge({ lineType }: { lineType?: PhoneLineType | null }) {
  if (!lineType || lineType === "UNKNOWN") return null;
  return (
    <span className="inline-flex items-center rounded-full border border-line bg-ink/5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-ink-mute">
      {lineType.toLowerCase()}
    </span>
  );
}
