"use client";

import { useId } from "react";

// ── HorizontalBar ──────────────────────────────────────────────────────────
// A horizontal bar chart with proportional fills. Used for grade distributions,
// category counts, country lists, etc.

interface BarDatum {
  label: string;
  value: number;
  href?: string;
  highlight?: boolean;
}

export function HorizontalBars({
  data,
  maxValue,
  unit = "",
  valueFormatter,
}: {
  data: BarDatum[];
  maxValue?: number;
  unit?: string;
  valueFormatter?: (v: number) => string;
}) {
  const max = maxValue ?? Math.max(...data.map((d) => d.value), 1);
  const format = valueFormatter ?? ((v: number) => v.toLocaleString() + unit);

  return (
    <ul className="space-y-3">
      {data.map((d, i) => {
        const pct = max === 0 ? 0 : (d.value / max) * 100;
        const content = (
          <div className="grid grid-cols-[120px_1fr_60px] items-center gap-4 group">
            <span className="text-sm truncate text-ink-soft">{d.label}</span>
            <div className="h-1.5 bg-paper-mute overflow-hidden">
              <div
                className={`h-full transition-all duration-700 ease-out ${
                  d.highlight ? "bg-ember" : "bg-ink/70"
                }`}
                style={{
                  width: `${pct}%`,
                  transitionDelay: `${i * 40}ms`,
                }}
              />
            </div>
            <span className="font-mono text-sm text-right tabular-nums text-ink-mute">
              {format(d.value)}
            </span>
          </div>
        );
        return (
          <li key={d.label}>
            {d.href ? (
              <a
                href={d.href}
                className="block hover:bg-paper-mute/40 transition-colors -mx-2 px-2 py-0.5"
              >
                {content}
              </a>
            ) : (
              content
            )}
          </li>
        );
      })}
    </ul>
  );
}

// ── DonutChart ─────────────────────────────────────────────────────────────
// Radial donut with center label. Used for grade distribution.

interface DonutSegment {
  label: string;
  value: number;
  color: string; // Tailwind class e.g. "text-ember"
}

export function DonutChart({
  data,
  size = 200,
  thickness = 22,
  centerLabel,
  centerValue,
}: {
  data: DonutSegment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const cx = size / 2;
  const cy = size / 2;

  // Build segments
  let offset = 0;

  return (
    <div className="flex flex-col md:flex-row items-center gap-8">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
          aria-hidden
        >
          {/* Background ring */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={thickness}
            className="text-paper-mute"
          />
          {/* Segments */}
          {data.map((seg, i) => {
            if (seg.value === 0 || total === 0) return null;
            const portion = seg.value / total;
            const dash = circumference * portion;
            const gap = circumference - dash;
            const rotate = (offset / total) * 360;
            offset += seg.value;
            return (
              <circle
                key={`${seg.label}-${i}`}
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke="currentColor"
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${gap}`}
                strokeLinecap="butt"
                className={`${seg.color} transition-all duration-700 ease-out`}
                style={{
                  transformOrigin: `${cx}px ${cy}px`,
                  transform: `rotate(${rotate}deg)`,
                  transitionDelay: `${i * 60}ms`,
                }}
              />
            );
          })}
        </svg>
        {(centerLabel || centerValue) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            {centerValue && (
              <span className="display text-4xl">{centerValue}</span>
            )}
            {centerLabel && (
              <span className="text-xs font-mono uppercase tracking-wider text-ink-mute mt-1">
                {centerLabel}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <ul className="space-y-2 text-sm">
        {data.map((seg) => {
          const pct = total === 0 ? 0 : (seg.value / total) * 100;
          return (
            <li key={seg.label} className="flex items-center gap-3">
              <span
                className={`status-dot ${seg.color.replace("text-", "bg-")}`}
              />
              <span className="text-ink-soft">{seg.label}</span>
              <span className="ml-auto font-mono text-xs text-ink-mute tabular-nums">
                {seg.value.toLocaleString()} · {pct.toFixed(0)}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Sparkline ──────────────────────────────────────────────────────────────
// Minimal area+line chart for time series. Single-color stroke + soft fill.

export function Sparkline({
  values,
  width = 280,
  height = 60,
  strokeClassName = "stroke-ember",
  fillClassName = "text-ember",
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  strokeClassName?: string;
  fillClassName?: string;
  label?: string;
}) {
  const id = useId();
  if (values.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-xs text-ink-ghost"
        style={{ height }}
      >
        Not enough data
      </div>
    );
  }

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);

  const points = values.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return [x, y] as const;
  });

  const path = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
    .join(" ");

  const areaPath = `${path} L${width},${height} L0,${height} Z`;

  return (
    <div>
      {label && (
        <div className="flex items-baseline justify-between mb-3">
          <span className="text-xs font-mono uppercase tracking-wider text-ink-mute">
            {label}
          </span>
          <span className="display text-2xl">
            {values[values.length - 1].toLocaleString()}
          </span>
        </div>
      )}
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={`spark-${id}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" className={fillClassName} stopOpacity="0.25" />
            <stop offset="100%" className={fillClassName} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#spark-${id})`} />
        <path
          d={path}
          fill="none"
          className={strokeClassName}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

// ── KpiStat ────────────────────────────────────────────────────────────────
// Big editorial number with optional delta indicator.

export function KpiStat({
  label,
  value,
  meta,
  hint,
  delay = 0,
}: {
  label: string;
  value: string | number;
  meta?: string;
  hint?: string;
  delay?: number;
}) {
  return (
    <div
      className="py-8 first:pt-0 animate-fade-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </div>
      <div className="display text-5xl md:text-6xl">{value.toLocaleString()}</div>
      {meta && (
        <div className="text-sm text-ink-mute mt-2 font-mono">{meta}</div>
      )}
      {hint && <p className="text-sm text-ink-mute mt-3">{hint}</p>}
    </div>
  );
}