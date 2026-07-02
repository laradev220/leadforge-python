import type { LeadScore } from "@/lib/types";

interface Factor {
  key: keyof Pick<
    LeadScore,
    | "website_opportunity_score"
    | "social_activity_score"
    | "contact_quality_score"
    | "review_score"
    | "business_validation_score"
  >;
  label: string;
  description: string;
}

const FACTORS: Factor[] = [
  {
    key: "website_opportunity_score",
    label: "Website opportunity",
    description: "Business has weak/missing website — pitch opportunity",
  },
  {
    key: "social_activity_score",
    label: "Social activity",
    description: "Active social profiles across platforms",
  },
  {
    key: "contact_quality_score",
    label: "Contact quality",
    description: "Verified emails, phone numbers, forms",
  },
  {
    key: "review_score",
    label: "Reputation",
    description: "Google reviews and rating",
  },
  {
    key: "business_validation_score",
    label: "Validation",
    description: "Address completeness, claimed listing, category match",
  },
];

const WEIGHT: Record<Factor["key"], number> = {
  website_opportunity_score: 0.30,
  social_activity_score: 0.15,
  contact_quality_score: 0.25,
  review_score: 0.15,
  business_validation_score: 0.15,
};

function clamp(value: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, value));
}

export function ScoreBreakdown({ score }: { score: LeadScore | null }) {
  if (!score) {
    return (
      <div className="py-12 text-center border-y border-line">
        <p className="display text-display-md mb-3">No score yet</p>
        <p className="text-ink-mute text-sm">
          Score will be calculated once workers finish enriching this business.
        </p>
      </div>
    );
  }

  // Compute weighted score for transparency
  const computed = FACTORS.reduce((sum, f) => {
    return sum + clamp(Number(score[f.key]) || 0) * WEIGHT[f.key];
  }, 0);

  return (
    <div className="grid lg:grid-cols-[280px_1fr] gap-12 items-start">
      <ScoreDial score={score.score} computed={computed} grade={score.grade} />
      <FactorList score={score} />
    </div>
  );
}

function ScoreDial({
  score,
  computed,
  grade,
}: {
  score: number;
  computed: number;
  grade: string | null;
}) {
  const radius = 100;
  const circumference = 2 * Math.PI * radius;
  const pct = clamp(score) / 100;
  const dash = circumference * pct;

  return (
    <div className="flex flex-col items-center text-center">
      <div className="relative" style={{ width: 240, height: 240 }}>
        <svg
          width={240}
          height={240}
          viewBox="0 0 240 240"
          className="-rotate-90"
          aria-hidden
        >
          <circle
            cx={120}
            cy={120}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={1}
            className="text-line"
          />
          <circle
            cx={120}
            cy={120}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeDasharray={`${dash} ${circumference - dash}`}
            strokeLinecap="round"
            className="text-ember transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="display text-6xl leading-none">{Math.round(score)}</span>
          <span className="text-xs font-mono uppercase tracking-wider text-ink-mute mt-2">
            Score
          </span>
        </div>
      </div>

      {grade && (
        <div className="mt-4 inline-flex items-center gap-2">
          <span className="text-xs font-mono uppercase tracking-wider text-ink-mute">
            Grade
          </span>
          <span
            className={`display text-3xl ${
              grade === "A+" || grade === "A"
                ? "text-ember"
                : grade === "B"
                  ? "text-ink"
                  : "text-ink-mute"
            }`}
          >
            {grade}
          </span>
        </div>
      )}

      <p className="text-xs text-ink-ghost font-mono mt-3">
        weighted · {Math.round(computed)} computed
      </p>
    </div>
  );
}

function FactorList({ score }: { score: LeadScore }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-line pb-4">
        <h3 className="text-xs font-mono uppercase tracking-wider text-ink-mute">
          Score breakdown
        </h3>
        <span className="text-xs text-ink-ghost font-mono">
          weighted · 0–100
        </span>
      </div>

      <ul className="space-y-5">
        {FACTORS.map((f) => {
          const value = clamp(Number(score[f.key]) || 0);
          const weight = WEIGHT[f.key];
          return (
            <li key={f.key}>
              <div className="flex items-baseline justify-between mb-1.5">
                <div>
                  <span className="font-display text-base">{f.label}</span>
                  <span className="ml-2 text-xs text-ink-ghost font-mono">
                    {Math.round(weight * 100)}%
                  </span>
                </div>
                <span className="font-mono text-sm tabular-nums">
                  {Math.round(value)}
                </span>
              </div>
              <div className="h-1 bg-paper-mute overflow-hidden">
                <div
                  className="h-full bg-ember transition-all duration-700 ease-out"
                  style={{ width: `${value}%` }}
                />
              </div>
              <p className="text-xs text-ink-mute mt-1.5">{f.description}</p>
            </li>
          );
        })}
      </ul>

      {score.notes && (
        <div className="border-t border-line pt-5">
          <h4 className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
            Notes
          </h4>
          <p className="text-sm text-ink-soft">{score.notes}</p>
        </div>
      )}
    </div>
  );
}

// Compact version for list rows
export function ScorePill({
  score,
  grade,
}: {
  score: number | null | undefined;
  grade: string | null;
}) {
  if (score === null || score === undefined) {
    return (
      <span className="status text-ink-ghost">
        <span className="status-dot bg-ink-ghost" /> unscored
      </span>
    );
  }
  const tier =
    score >= 80 ? "bg-ember" : score >= 50 ? "bg-moss" : "bg-ink-ghost";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-display text-2xl leading-none">
        {grade ?? Math.round(score)}
      </span>
      <span className="status text-ink-mute">
        <span className={`status-dot ${tier}`} />
        {Math.round(score)}
      </span>
    </span>
  );
}