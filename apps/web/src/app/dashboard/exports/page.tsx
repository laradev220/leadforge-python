"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowUpRight, Download, Loader2, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import type { ExportRecord } from "@/lib/types";
import {
  EXPORT_FORMAT_LABELS,
  EXPORT_STATUS_COLORS,
  EXPORT_STATUS_LABELS,
} from "@/lib/format";
import { formatRelative } from "@/lib/utils";
import { CreateExportModal } from "./_components/create-export-modal";

export default function ExportsPage() {
  const token = useAuth((s) => s.token);
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.listExports();
      setExports(res.data);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while any export is processing
  useEffect(() => {
    const hasActive = exports.some(
      (e) => e.status === "PENDING" || e.status === "PROCESSING",
    );
    if (!hasActive) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }
    intervalRef.current = setInterval(load, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [exports, load]);

  function handleCreated() {
    load();
  }

  function handleDownload(exp: ExportRecord) {
    if (exp.status !== "COMPLETED") {
      toast.error("Export not ready yet");
      return;
    }
    // Direct download via temporary link with auth header injected via fetch
    downloadWithAuth(api.getExportDownloadUrl(exp.id), `leads.${exp.format.toLowerCase()}`);
  }

  async function downloadWithAuth(url: string, filename: string) {
    try {
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    }
  }

  const completedCount = exports.filter((e) => e.status === "COMPLETED").length;
  const processingCount = exports.filter(
    (e) => e.status === "PENDING" || e.status === "PROCESSING",
  ).length;

  return (
    <div className="space-y-12 animate-fade-up">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p className="status text-ink-mute mb-3">
            <span className="status-dot bg-ember" />
            {completedCount} ready · {processingCount} processing
          </p>
          <h1 className="display text-display-lg">Exports</h1>
          <p className="text-ink-mute mt-2 max-w-md">
            Download your leads in CSV, XLSX, or JSON. Workers process
            requests asynchronously — come back in a moment if your file is
            still queued.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="btn-solid"
        >
          <Plus size={14} /> New export
        </button>
      </header>

      <section>
        {loading && exports.length === 0 ? (
          <Skeleton />
        ) : error && exports.length === 0 ? (
          <div className="py-20 text-center border-y border-line">
            <p className="display text-display-md mb-3">Couldn't load</p>
            <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">{error}</p>
            <button onClick={load} className="btn-outline">
              Try again
            </button>
          </div>
        ) : exports.length === 0 ? (
          <EmptyState onCreate={() => setModalOpen(true)} />
        ) : (
          <ul className="border-y border-line divide-y divide-line">
            {exports.map((exp) => (
              <ExportRow
                key={exp.id}
                exp={exp}
                onDownload={() => handleDownload(exp)}
              />
            ))}
          </ul>
        )}
      </section>

      <CreateExportModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}

function ExportRow({
  exp,
  onDownload,
}: {
  exp: ExportRecord;
  onDownload: () => void;
}) {
  const ready = exp.status === "COMPLETED";
  const active = exp.status === "PENDING" || exp.status === "PROCESSING";

  return (
    <li className="grid grid-cols-12 gap-4 items-center py-5 px-2">
      <div className="col-span-6 md:col-span-3 min-w-0">
        <div className="font-display text-lg">
          leads.{exp.format.toLowerCase()}
        </div>
        <div className="text-xs text-ink-mute font-mono mt-1">
          {formatRelative(exp.created_at)}
        </div>
      </div>

      <div className="col-span-3 md:col-span-2">
        <span className="font-mono text-xs uppercase tracking-wider text-ink-mute">
          {EXPORT_FORMAT_LABELS[exp.format]}
        </span>
      </div>

      <div className="col-span-3 md:col-span-2 font-mono text-sm tabular-nums">
        {exp.total_records > 0
          ? `${exp.total_records.toLocaleString()} records`
          : "—"}
      </div>

      <div className="col-span-6 md:col-span-3">
        <span className="status text-ink-mute">
          <span className={`status-dot ${EXPORT_STATUS_COLORS[exp.status]}`} />
          {EXPORT_STATUS_LABELS[exp.status].toLowerCase()}
          {active && (
            <Loader2 size={10} className="ml-1 animate-spin text-ember" />
          )}
        </span>
      </div>

      <div className="col-span-6 md:col-span-2 flex justify-end">
        <button
          type="button"
          onClick={onDownload}
          disabled={!ready}
          className={`btn-ghost text-sm ${ready ? "" : "opacity-30 pointer-events-none"}`}
        >
          <Download size={14} /> Download
          {ready && <ArrowUpRight size={12} />}
        </button>
      </div>
    </li>
  );
}

function Skeleton() {
  return (
    <div className="border-y border-line">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-12 gap-4 items-center py-5 px-2 border-b border-line last:border-b-0"
        >
          <div className="col-span-3 space-y-2">
            <div className="h-5 w-24 bg-paper-mute animate-pulse-soft" />
            <div className="h-3 w-16 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-3">
            <div className="h-3 w-12 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-3 w-16 bg-paper-mute animate-pulse-soft" />
          </div>
          <div className="col-span-2">
            <div className="h-3 w-14 bg-paper-mute animate-pulse-soft" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="py-20 text-center border-y border-line">
      <p className="display text-display-md mb-3">No exports yet</p>
      <p className="text-ink-mute text-sm max-w-sm mx-auto mb-8">
        Create your first export to download leads in CSV, XLSX, or JSON.
      </p>
      <button onClick={onCreate} className="btn-solid">
        <Plus size={14} /> New export
      </button>
    </div>
  );
}