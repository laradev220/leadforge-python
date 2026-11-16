"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Upload } from "lucide-react";
import { api } from "@/lib/api";
import type { Suppression } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

const KIND_OPTIONS: Suppression["kind"][] = ["EMAIL", "PHONE", "DOMAIN"];

export default function SuppressionsPage() {
  const [entries, setEntries] = useState<Suppression[]>([]);
  const [loading, setLoading] = useState(true);
  const [kind, setKind] = useState<Suppression["kind"]>("EMAIL");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("manual");
  const [note, setNote] = useState("");
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listSuppressions();
      setEntries(res.data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load suppressions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setBusy(true);
    try {
      await api.addSuppression({ kind, value: value.trim(), reason, note: note || undefined });
      toast.success("Suppression added");
      setValue("");
      setNote("");
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setBusy(false);
    }
  }

  async function bulkImport() {
    const lines = bulkText
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length === 0) return;
    const parsed = lines.map((line) => {
      const [first, second] = line.split(",").map((part) => part.trim());
      if (second && KIND_OPTIONS.includes(first.toUpperCase() as Suppression["kind"])) {
        return { kind: first.toUpperCase() as Suppression["kind"], value: second };
      }
      return { kind: "EMAIL" as const, value: first };
    });
    setBusy(true);
    try {
      const res = await api.bulkAddSuppressions(parsed);
      toast.success(`${res.data.added} added · ${res.data.skipped} duplicates`);
      setBulkText("");
      setBulkOpen(false);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Bulk import failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteSuppression(id);
      setEntries((rows) => rows.filter((row) => row.id !== id));
      toast.success("Removed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove");
    }
  }

  const filtered = entries.filter((entry) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      entry.value.toLowerCase().includes(q) ||
      entry.kind.toLowerCase().includes(q) ||
      entry.reason.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-10 animate-fade-up">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p className="status text-ink-mute mb-3">
            <span className="status-dot bg-ember" /> {entries.length} suppressed
          </p>
          <h1 className="display text-display-lg">Suppressions</h1>
          <p className="text-ink-mute mt-2 max-w-lg">
            Do-not-contact entries are enforced on every export. Emails, phone
            numbers, and whole domains are supported.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setBulkOpen((v) => !v)}
          className="btn-outline inline-flex items-center gap-2"
        >
          <Upload size={14} /> Bulk import
        </button>
      </header>

      <section className="grid lg:grid-cols-[1fr_360px] gap-10">
        <div className="space-y-4">
          <div className="flex items-center gap-3 border-y border-line py-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter entries…"
              className="w-full bg-transparent text-sm focus:outline-none"
            />
          </div>

          {loading ? (
            <div className="py-16 flex justify-center">
              <Loader2 size={18} className="animate-spin text-ink-mute" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-ink-mute text-sm border-b border-line">
              No suppressions yet.
            </div>
          ) : (
            <ul className="border-t border-line">
              {filtered.map((entry) => (
                <li
                  key={entry.id}
                  className="grid grid-cols-[80px_1fr_auto] gap-3 items-center py-3 border-b border-line"
                >
                  <span className="font-mono text-[10px] uppercase tracking-wider text-ink-mute">
                    {entry.kind}
                  </span>
                  <div className="min-w-0">
                    <div className="font-mono text-sm break-all">{entry.value}</div>
                    <div className="text-xs text-ink-mute">
                      {entry.reason}
                      {entry.note ? ` · ${entry.note}` : ""} ·{" "}
                      {formatRelative(entry.created_at)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => remove(entry.id)}
                    className="text-ink-mute hover:text-ember transition-colors p-2"
                    aria-label={`Remove ${entry.value}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {bulkOpen && (
            <div className="border border-line p-4 space-y-3">
              <p className="text-xs font-mono uppercase tracking-wider text-ink-mute">
                One per line — value or kind,value
              </p>
              <textarea
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                rows={6}
                placeholder={"jane@example.com\nPHONE,+923001234567\nDOMAIN,competitor.com"}
                className="w-full bg-transparent border border-line p-3 font-mono text-xs focus:outline-none focus:border-ember"
              />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setBulkOpen(false)} className="btn-ghost">
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={bulkImport}
                  disabled={busy || !bulkText.trim()}
                  className="btn-solid"
                >
                  {busy ? <Loader2 size={14} className="animate-spin" /> : "Import"}
                </button>
              </div>
            </div>
          )}
        </div>

        <aside>
          <form onSubmit={add} className="border border-line p-5 space-y-4">
            <h2 className="display text-lg">Add entry</h2>
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Kind
              </label>
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as Suppression["kind"])}
                className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
              >
                {KIND_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option.toLowerCase()}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Value
              </label>
              <input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="name@company.com"
                className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
              />
            </div>
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Reason
              </label>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
              />
            </div>
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
                Note (optional)
              </label>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-2 text-sm focus:outline-none focus:border-ember"
              />
            </div>
            <button type="submit" disabled={busy || !value.trim()} className="btn-solid w-full justify-center">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <><Plus size={14} /> Add suppression</>}
            </button>
          </form>
        </aside>
      </section>
    </div>
  );
}
