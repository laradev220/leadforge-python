"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Copy, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type {
  IntegrationKind,
  IntegrationSummary,
  WebhookDelivery,
  WebhookEndpoint,
  WebhookEvent,
} from "@/lib/types";
import { formatRelative } from "@/lib/utils";

const EVENTS: WebhookEvent[] = [
  "search.completed",
  "export.completed",
  "verification.completed",
  "schedule.run",
];

export default function IntegrationsPage() {
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<WebhookEvent[]>(["export.completed"]);
  const [busy, setBusy] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<Record<string, WebhookDelivery[]>>({});
  const [copied, setCopied] = useState<string | null>(null);

  const [hubspotToken, setHubspotToken] = useState("");
  const [sheetsJson, setSheetsJson] = useState("");
  const [sheetId, setSheetId] = useState("");
  const [sheetRange, setSheetRange] = useState("Leads!A1");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hooks, integrationsRes] = await Promise.all([
        api.listWebhooks(),
        api.listIntegrations(),
      ]);
      setWebhooks(hooks.data);
      setIntegrations(integrationsRes.data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function integration(kind: IntegrationKind) {
    return integrations.find((row) => row.kind === kind);
  }

  async function addWebhook(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || events.length === 0) return;
    setBusy("webhook");
    try {
      const res = await api.createWebhook({ url: url.trim(), events });
      setWebhooks((rows) => [res.data, ...rows]);
      setUrl("");
      toast.success("Webhook created");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create webhook");
    } finally {
      setBusy(null);
    }
  }

  async function toggleWebhook(endpoint: WebhookEndpoint) {
    try {
      const res = await api.updateWebhook(endpoint.id, { active: !endpoint.active });
      setWebhooks((rows) => rows.map((row) => (row.id === endpoint.id ? res.data : row)));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update");
    }
  }

  async function deleteWebhook(endpoint: WebhookEndpoint) {
    if (!window.confirm(`Delete webhook ${endpoint.url}?`)) return;
    try {
      await api.deleteWebhook(endpoint.id);
      setWebhooks((rows) => rows.filter((row) => row.id !== endpoint.id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  async function rotate(endpoint: WebhookEndpoint) {
    try {
      const res = await api.rotateWebhookSecret(endpoint.id);
      setWebhooks((rows) => rows.map((row) => (row.id === endpoint.id ? res.data : row)));
      toast.success("Signing secret rotated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to rotate");
    }
  }

  async function showDeliveries(endpoint: WebhookEndpoint) {
    if (deliveries[endpoint.id]) {
      setDeliveries((current) => {
        const next = { ...current };
        delete next[endpoint.id];
        return next;
      });
      return;
    }
    try {
      const res = await api.listWebhookDeliveries(endpoint.id, 8);
      setDeliveries((current) => ({ ...current, [endpoint.id]: res.data }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load deliveries");
    }
  }

  async function copySecret(endpoint: WebhookEndpoint) {
    await navigator.clipboard.writeText(endpoint.secret);
    setCopied(endpoint.id);
    setTimeout(() => setCopied(null), 1500);
  }

  async function saveIntegration(kind: IntegrationKind) {
    setBusy(kind);
    try {
      const config =
        kind === "HUBSPOT"
          ? { token: hubspotToken.trim() }
          : {
              service_account_json: sheetsJson,
              spreadsheet_id: sheetId.trim(),
              range: sheetRange.trim() || "Leads!A1",
            };
      const res = await api.saveIntegration(kind, config);
      setIntegrations((rows) => [
        ...rows.filter((row) => row.kind !== kind),
        res.data,
      ]);
      toast.success(`${kind.toLowerCase()} saved`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setBusy(null);
    }
  }

  async function testIntegration(kind: IntegrationKind) {
    setBusy(`${kind}-test`);
    try {
      const res = await api.testIntegration(kind);
      toast.success(res.data.detail);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusy(null);
    }
  }

  async function pushIntegration(kind: IntegrationKind) {
    setBusy(`${kind}-push`);
    try {
      const res = await api.pushIntegration(kind, { limit: 50 });
      toast.success(`${res.data.pushed} pushed · ${res.data.failed} failed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Push failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-12 animate-fade-up">
      <header>
        <p className="status text-ink-mute mb-3">
          <span className="status-dot bg-ember" /> {webhooks.length} webhooks ·{" "}
          {integrations.length} integrations
        </p>
        <h1 className="display text-display-lg">Integrations</h1>
        <p className="text-ink-mute mt-2 max-w-xl">
          Push verified leads into your stack. Webhooks are signed with HMAC-SHA256;
          CRM and Sheets credentials are encrypted at rest.
        </p>
      </header>

      {/* Webhooks */}
      <section className="space-y-5">
        <SectionTitle title="Webhooks" meta="POST · HMAC-SHA256 signed" />
        <form onSubmit={addWebhook} className="border border-line p-5 space-y-4">
          <div className="grid md:grid-cols-[1fr_auto] gap-3">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://hooks.example.com/leadforge"
              className="field-input"
            />
            <button type="submit" disabled={busy === "webhook"} className="btn-solid">
              {busy === "webhook" ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <><Plus size={14} /> Add webhook</>
              )}
            </button>
          </div>
          <div className="flex flex-wrap gap-3">
            {EVENTS.map((event) => (
              <label key={event} className="inline-flex items-center gap-2 text-xs font-mono">
                <input
                  type="checkbox"
                  className="accent-ember"
                  checked={events.includes(event)}
                  onChange={(e) =>
                    setEvents((current) =>
                      e.target.checked
                        ? [...current, event]
                        : current.filter((value) => value !== event),
                    )
                  }
                />
                {event}
              </label>
            ))}
          </div>
        </form>

        {loading ? (
          <Loader2 size={18} className="animate-spin text-ink-mute" />
        ) : webhooks.length === 0 ? (
          <p className="text-sm text-ink-mute border-y border-line py-6">
            No webhooks yet.
          </p>
        ) : (
          <ul className="border-t border-line">
            {webhooks.map((endpoint) => (
              <li key={endpoint.id} className="border-b border-line py-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      endpoint.active ? "bg-moss" : "bg-ink-ghost"
                    }`}
                  />
                  <span className="font-mono text-sm break-all flex-1 min-w-0">
                    {endpoint.url}
                  </span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-ink-mute">
                    {endpoint.events.join(" · ")}
                  </span>
                  {endpoint.failure_count > 0 && (
                    <span className="text-[10px] font-mono text-red-700">
                      {endpoint.failure_count} failures
                    </span>
                  )}
                  <button
                    onClick={() => toggleWebhook(endpoint)}
                    className="text-xs font-mono uppercase tracking-wider text-ink-mute hover:text-ink"
                  >
                    {endpoint.active ? "pause" : "resume"}
                  </button>
                  <button
                    onClick={() => showDeliveries(endpoint)}
                    className="text-xs font-mono uppercase tracking-wider text-ink-mute hover:text-ink"
                  >
                    deliveries
                  </button>
                  <button
                    onClick={() => rotate(endpoint)}
                    className="text-ink-mute hover:text-ink"
                    aria-label="Rotate secret"
                  >
                    <RefreshCw size={13} />
                  </button>
                  <button
                    onClick={() => copySecret(endpoint)}
                    className="text-ink-mute hover:text-ink"
                    aria-label="Copy secret"
                  >
                    {copied === endpoint.id ? <Check size={13} /> : <Copy size={13} />}
                  </button>
                  <button
                    onClick={() => deleteWebhook(endpoint)}
                    className="text-ink-mute hover:text-ember"
                    aria-label="Delete webhook"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                {deliveries[endpoint.id] && (
                  <ul className="mt-3 pl-4 space-y-1">
                    {deliveries[endpoint.id].length === 0 ? (
                      <li className="text-xs text-ink-mute">No deliveries yet.</li>
                    ) : (
                      deliveries[endpoint.id].map((delivery) => (
                        <li
                          key={delivery.id}
                          className="text-[11px] font-mono text-ink-mute flex gap-3"
                        >
                          <span
                            className={
                              delivery.status === "SUCCESS"
                                ? "text-emerald-700"
                                : delivery.status === "RETRYING"
                                  ? "text-amber-700"
                                  : "text-red-700"
                            }
                          >
                            {delivery.status.toLowerCase()}
                          </span>
                          <span>{delivery.event}</span>
                          <span>{delivery.response_code ?? "—"}</span>
                          <span>{formatRelative(delivery.created_at)}</span>
                          {delivery.error && <span className="truncate">{delivery.error}</span>}
                        </li>
                      ))
                    )}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* HubSpot */}
      <section className="grid lg:grid-cols-2 gap-8">
        <div className="border border-line p-5 space-y-4">
          <SectionTitle
            title="HubSpot"
            meta={integration("HUBSPOT")?.summary ?? "not configured"}
          />
          <input
            value={hubspotToken}
            onChange={(e) => setHubspotToken(e.target.value)}
            placeholder="Private app token (pat-…)"
            type="password"
            className="field-input"
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => saveIntegration("HUBSPOT")}
              disabled={busy === "HUBSPOT" || !hubspotToken.trim()}
              className="btn-solid"
            >
              Save
            </button>
            <button
              onClick={() => testIntegration("HUBSPOT")}
              disabled={!integration("HUBSPOT") || busy === "HUBSPOT-test"}
              className="btn-outline"
            >
              Test
            </button>
            <button
              onClick={() => pushIntegration("HUBSPOT")}
              disabled={!integration("HUBSPOT") || busy === "HUBSPOT-push"}
              className="btn-outline"
            >
              Push 50 leads
            </button>
          </div>
          <p className="text-xs text-ink-mute">
            Creates/updates companies by domain and contacts by email; duplicates are matched.
          </p>
        </div>

        {/* Sheets */}
        <div className="border border-line p-5 space-y-4">
          <SectionTitle
            title="Google Sheets"
            meta={integration("SHEETS")?.summary ?? "not configured"}
          />
          <textarea
            value={sheetsJson}
            onChange={(e) => setSheetsJson(e.target.value)}
            rows={4}
            placeholder='{"client_email":"…","private_key":"…","project_id":"…"}'
            className="field-input font-mono text-[11px]"
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              value={sheetId}
              onChange={(e) => setSheetId(e.target.value)}
              placeholder="Spreadsheet ID"
              className="field-input"
            />
            <input
              value={sheetRange}
              onChange={(e) => setSheetRange(e.target.value)}
              placeholder="Leads!A1"
              className="field-input"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => saveIntegration("SHEETS")}
              disabled={busy === "SHEETS" || !sheetsJson.trim() || !sheetId.trim()}
              className="btn-solid"
            >
              Save
            </button>
            <button
              onClick={() => testIntegration("SHEETS")}
              disabled={!integration("SHEETS") || busy === "SHEETS-test"}
              className="btn-outline"
            >
              Test
            </button>
            <button
              onClick={() => pushIntegration("SHEETS")}
              disabled={!integration("SHEETS") || busy === "SHEETS-push"}
              className="btn-outline"
            >
              Push 50 leads
            </button>
          </div>
          <p className="text-xs text-ink-mute">
            Writes a header row + one row per lead. The service account must have
            edit access to the sheet.
          </p>
        </div>
      </section>
    </div>
  );
}

function SectionTitle({ title, meta }: { title: string; meta?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="display text-xl">{title}</h2>
      {meta && (
        <span className="text-[10px] font-mono uppercase tracking-wider text-ink-mute truncate">
          {meta}
        </span>
      )}
    </div>
  );
}
