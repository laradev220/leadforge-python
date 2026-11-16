"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarClock, Loader2, Play, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ScheduleCadence, SearchSchedule } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function cadenceLabel(schedule: SearchSchedule): string {
  const time = `${String(schedule.hour).padStart(2, "0")}:${String(
    schedule.minute,
  ).padStart(2, "0")}`;
  if (schedule.cadence === "DAILY") return `Daily at ${time}`;
  if (schedule.cadence === "WEEKLY") {
    return `Weekly on ${WEEKDAYS[schedule.weekday ?? 0]} at ${time}`;
  }
  return `Monthly on day ${schedule.day_of_month ?? 1} at ${time}`;
}

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<SearchSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const [keyword, setKeyword] = useState("Dentist");
  const [location, setLocation] = useState("Peshawar");
  const [country, setCountry] = useState("PK");
  const [cadence, setCadence] = useState<ScheduleCadence>("WEEKLY");
  const [weekday, setWeekday] = useState(0);
  const [dayOfMonth, setDayOfMonth] = useState(1);
  const [hour, setHour] = useState(9);
  const [minute, setMinute] = useState(0);
  const [timezone, setTimezone] = useState("Asia/Karachi");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listSchedules();
      setSchedules(res.data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createSchedule(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createSchedule({
        keyword: keyword.trim(),
        location: location.trim(),
        country: country.trim().toUpperCase() || undefined,
        cadence,
        hour,
        minute,
        weekday: cadence === "WEEKLY" ? weekday : undefined,
        day_of_month: cadence === "MONTHLY" ? dayOfMonth : undefined,
        timezone,
      });
      toast.success("Schedule created");
      setFormOpen(false);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create schedule");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(schedule: SearchSchedule) {
    try {
      await api.updateSchedule(schedule.id, { enabled: !schedule.enabled });
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update");
    }
  }

  async function runNow(schedule: SearchSchedule) {
    try {
      await api.runScheduleNow(schedule.id);
      toast.success("Search queued");
      setTimeout(load, 1500);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to run");
    }
  }

  async function remove(schedule: SearchSchedule) {
    if (!window.confirm(`Delete the ${schedule.keyword} schedule?`)) return;
    try {
      await api.deleteSchedule(schedule.id);
      setSchedules((rows) => rows.filter((row) => row.id !== schedule.id));
      toast.success("Schedule deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  return (
    <div className="space-y-10 animate-fade-up">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p className="status text-ink-mute mb-3">
            <span className="status-dot bg-ember" /> {schedules.length} schedules
          </p>
          <h1 className="display text-display-lg">Schedules</h1>
          <p className="text-ink-mute mt-2 max-w-lg">
            Recurring searches run on their own. Each run creates a search job,
            discovers new businesses, and enriches them.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setFormOpen((v) => !v)}
          className="btn-solid inline-flex items-center gap-2"
        >
          <Plus size={14} /> New schedule
        </button>
      </header>

      {formOpen && (
        <form
          onSubmit={createSchedule}
          className="border border-line p-5 grid md:grid-cols-4 gap-4"
        >
          <Field label="Keyword">
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              required
              className="field-input"
            />
          </Field>
          <Field label="Location">
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
              className="field-input"
            />
          </Field>
          <Field label="Country">
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
              maxLength={2}
              className="field-input"
            />
          </Field>
          <Field label="Cadence">
            <select
              value={cadence}
              onChange={(e) => setCadence(e.target.value as ScheduleCadence)}
              className="field-input"
            >
              <option value="DAILY">Daily</option>
              <option value="WEEKLY">Weekly</option>
              <option value="MONTHLY">Monthly</option>
            </select>
          </Field>

          {cadence === "WEEKLY" && (
            <Field label="Weekday">
              <select
                value={weekday}
                onChange={(e) => setWeekday(Number(e.target.value))}
                className="field-input"
              >
                {WEEKDAYS.map((day, index) => (
                  <option key={day} value={index}>
                    {day}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {cadence === "MONTHLY" && (
            <Field label="Day of month">
              <input
                type="number"
                min={1}
                max={28}
                value={dayOfMonth}
                onChange={(e) => setDayOfMonth(Number(e.target.value))}
                className="field-input"
              />
            </Field>
          )}
          <Field label="Hour (0-23)">
            <input
              type="number"
              min={0}
              max={23}
              value={hour}
              onChange={(e) => setHour(Number(e.target.value))}
              className="field-input"
            />
          </Field>
          <Field label="Minute">
            <input
              type="number"
              min={0}
              max={59}
              value={minute}
              onChange={(e) => setMinute(Number(e.target.value))}
              className="field-input"
            />
          </Field>
          <Field label="Timezone">
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="field-input"
            />
          </Field>

          <div className="md:col-span-4 flex justify-end gap-3 border-t border-line pt-4">
            <button type="button" onClick={() => setFormOpen(false)} className="btn-ghost">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="btn-solid">
              {saving ? <Loader2 size={14} className="animate-spin" /> : "Create schedule"}
            </button>
          </div>
        </form>
      )}

      <section>
        {loading ? (
          <div className="py-16 flex justify-center">
            <Loader2 size={18} className="animate-spin text-ink-mute" />
          </div>
        ) : schedules.length === 0 ? (
          <div className="py-16 text-center border-y border-line">
            <p className="display text-display-md mb-2">No schedules yet</p>
            <p className="text-ink-mute text-sm">
              Create one to keep a territory warm without manual searches.
            </p>
          </div>
        ) : (
          <ul className="border-t border-line">
            {schedules.map((schedule) => (
              <li
                key={schedule.id}
                className="grid grid-cols-12 gap-4 items-center py-5 border-b border-line"
              >
                <div className="col-span-12 md:col-span-4 min-w-0">
                  <div className="display text-lg truncate">{schedule.keyword}</div>
                  <div className="text-xs text-ink-mute font-mono">
                    {schedule.location}
                    {schedule.country ? ` · ${schedule.country}` : ""} ·{" "}
                    {schedule.timezone}
                  </div>
                </div>
                <div className="col-span-6 md:col-span-3 text-sm">
                  <div className="inline-flex items-center gap-2">
                    <CalendarClock size={14} className="text-ink-ghost" />
                    {cadenceLabel(schedule)}
                  </div>
                </div>
                <div className="col-span-6 md:col-span-2 text-xs font-mono text-ink-mute">
                  <div>
                    next {schedule.enabled ? formatRelative(schedule.next_run_at) : "paused"}
                  </div>
                  {schedule.last_run_at && (
                    <div>last {formatRelative(schedule.last_run_at)}</div>
                  )}
                </div>
                <div className="col-span-6 md:col-span-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => toggle(schedule)}
                    className={`rounded-full border px-3 py-1 text-[10px] font-mono uppercase tracking-wider ${
                      schedule.enabled
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : "border-line text-ink-mute"
                    }`}
                  >
                    {schedule.enabled ? "active" : "paused"}
                  </button>
                  <button
                    type="button"
                    onClick={() => runNow(schedule)}
                    className="text-ink-mute hover:text-ember p-2"
                    aria-label="Run now"
                  >
                    <Play size={14} />
                  </button>
                </div>
                <div className="col-span-6 md:col-span-1 flex justify-end">
                  <button
                    type="button"
                    onClick={() => remove(schedule)}
                    className="text-ink-mute hover:text-ember p-2"
                    aria-label="Delete schedule"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
        {label}
      </span>
      {children}
    </label>
  );
}
