import type {
  ApiError,
  AuthSuccess,
  Business,
  BusinessListFilters,
  Contact,
  DashboardStats,
  EngineActivity,
  ExportFilters,
  ExportFormat,
  ExportRecord,
  ScheduleCadence,
  ScheduleRun,
  SearchJobProgress,
  IntegrationKind,
  IntegrationSummary,
  SearchSchedule,
  Suppression,
  WebhookDelivery,
  WebhookEndpoint,
  WebhookEvent,
  VerificationCapabilities,
  GradeDistribution,
  Lead,
  LeadListFilters,
  LoginPayload,
  PaginatedResponse,
  RegisterPayload,
  SearchJob,
  SearchJobStatus,
  SearchJobWithBusinesses,
  SingleResponse,
  SocialProfile,
  SocialProfileListFilters,
  SocialProfileWithBusiness,
  User,
  Website,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_BASE = `${API_URL}/api/v1`;

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    try {
      const raw = localStorage.getItem("leadforge-auth");
      if (!raw) return null;
      return JSON.parse(raw).state?.token ?? null;
    } catch {
      return null;
    }
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init.headers as Record<string, string>),
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const err = data as ApiError | null;
      const message = err?.error?.message || `Request failed (${res.status})`;
      throw new Error(message);
    }

    return data as T;
  }

  // ── Auth ────────────────────────────────────────────────────────────────

  async login(payload: LoginPayload): Promise<AuthSuccess> {
    const res = await this.request<{ data: AuthSuccess }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return res.data;
  }

  async register(payload: RegisterPayload): Promise<AuthSuccess> {
    const res = await this.request<{ data: AuthSuccess }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return res.data;
  }

  async me(): Promise<SingleResponse<User>> {
    return this.request<SingleResponse<User>>("/auth/me");
  }

  async updateProfile(payload: {
    full_name?: string;
    email?: string;
  }): Promise<SingleResponse<User>> {
    return this.request<SingleResponse<User>>("/auth/me", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  async changePassword(payload: {
    current_password: string;
    new_password: string;
  }): Promise<SingleResponse<{ changed: true }>> {
    return this.request("/auth/password", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  // ── Search Jobs ─────────────────────────────────────────────────────────

  async createSearchJob(payload: {
    keyword: string;
    location: string;
    radius_km?: number;
    country?: string;
  }): Promise<SingleResponse<{ job_id: string; status: SearchJobStatus }>> {
    return this.request("/search-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listWebhooks(): Promise<SingleResponse<WebhookEndpoint[]>> {
    return this.request<SingleResponse<WebhookEndpoint[]>>(`/webhooks`);
  }

  async createWebhook(payload: {
    url: string;
    events: WebhookEvent[];
  }): Promise<SingleResponse<WebhookEndpoint>> {
    return this.request(`/webhooks`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateWebhook(
    id: string,
    payload: { events?: WebhookEvent[]; active?: boolean; url?: string },
  ): Promise<SingleResponse<WebhookEndpoint>> {
    return this.request(`/webhooks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteWebhook(id: string): Promise<SingleResponse<{ deleted: true }>> {
    return this.request(`/webhooks/${id}`, { method: "DELETE" });
  }

  async rotateWebhookSecret(
    id: string,
  ): Promise<SingleResponse<WebhookEndpoint>> {
    return this.request(`/webhooks/${id}/rotate-secret`, { method: "POST" });
  }

  async listWebhookDeliveries(
    id: string,
    limit = 10,
  ): Promise<SingleResponse<WebhookDelivery[]>> {
    return this.request<SingleResponse<WebhookDelivery[]>>(
      `/webhooks/${id}/deliveries?limit=${limit}`,
    );
  }

  async listIntegrations(): Promise<SingleResponse<IntegrationSummary[]>> {
    return this.request<SingleResponse<IntegrationSummary[]>>(`/integrations`);
  }

  async saveIntegration(
    kind: IntegrationKind,
    config: Record<string, unknown>,
  ): Promise<SingleResponse<IntegrationSummary>> {
    return this.request(`/integrations/${kind}`, {
      method: "PUT",
      body: JSON.stringify({ config }),
    });
  }

  async testIntegration(
    kind: IntegrationKind,
  ): Promise<SingleResponse<{ ok: boolean; detail: string }>> {
    return this.request(`/integrations/${kind}/test`, { method: "POST" });
  }

  async pushIntegration(
    kind: IntegrationKind,
    payload: { limit?: number; score_min?: number; verified_email?: boolean } = {},
  ): Promise<SingleResponse<{ pushed: number; failed: number; detail: string }>> {
    return this.request(`/integrations/${kind}/push`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async deleteIntegration(
    kind: IntegrationKind,
  ): Promise<SingleResponse<{ deleted: true }>> {
    return this.request(`/integrations/${kind}`, { method: "DELETE" });
  }

  async listSchedules(): Promise<SingleResponse<SearchSchedule[]>> {
    return this.request<SingleResponse<SearchSchedule[]>>(`/schedules`);
  }

  async createSchedule(payload: {
    keyword: string;
    location: string;
    country?: string;
    radius_km?: number;
    cadence: ScheduleCadence;
    hour: number;
    minute: number;
    weekday?: number;
    day_of_month?: number;
    timezone: string;
    enabled?: boolean;
  }): Promise<SingleResponse<SearchSchedule>> {
    return this.request(`/schedules`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateSchedule(
    id: string,
    payload: Record<string, unknown>,
  ): Promise<SingleResponse<SearchSchedule>> {
    return this.request(`/schedules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteSchedule(id: string): Promise<SingleResponse<{ deleted: true }>> {
    return this.request(`/schedules/${id}`, { method: "DELETE" });
  }

  async runScheduleNow(
    id: string,
  ): Promise<SingleResponse<{ job_id: string }>> {
    return this.request(`/schedules/${id}/run`, { method: "POST" });
  }

  async listScheduleRuns(
    id: string,
    limit = 5,
  ): Promise<SingleResponse<ScheduleRun[]>> {
    return this.request<SingleResponse<ScheduleRun[]>>(
      `/schedules/${id}/runs?limit=${limit}`,
    );
  }

  async listSearchJobs(
    page = 1,
    limit = 50,
    status?: SearchJobStatus,
  ): Promise<PaginatedResponse<SearchJob>> {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (status) params.set("status", status);
    return this.request<PaginatedResponse<SearchJob>>(
      `/search-jobs?${params.toString()}`,
    );
  }

  async getSearchJob(id: string): Promise<SingleResponse<SearchJobWithBusinesses>> {
    return this.request<SingleResponse<SearchJobWithBusinesses>>(`/search-jobs/${id}`);
  }

  async cancelSearchJob(id: string): Promise<SingleResponse<{ cancelled: true }>> {
    return this.request(`/search-jobs/${id}/cancel`, { method: "POST" });
  }

  // ── Businesses ──────────────────────────────────────────────────────────

  async listBusinesses(
    filters: BusinessListFilters = {},
  ): Promise<PaginatedResponse<Business>> {
    const params = new URLSearchParams();
    const entries: Array<[string, unknown]> = [
      ["page", filters.page ?? 1],
      ["limit", filters.limit ?? 50],
      ["name", filters.name],
      ["city", filters.city],
      ["country", filters.country],
      ["category", filters.category],
      ["website_status", filters.website_status],
      ["min_rating", filters.min_rating],
      ["max_rating", filters.max_rating],
    ];
    for (const [key, value] of entries) {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    }
    return this.request<PaginatedResponse<Business>>(
      `/businesses?${params.toString()}`,
    );
  }

  async getBusiness(id: string): Promise<SingleResponse<Business>> {
    return this.request<SingleResponse<Business>>(`/businesses/${id}`);
  }

  async verifyBusiness(
    id: string,
    force = false,
  ): Promise<SingleResponse<{ queued: true }>> {
    return this.request(`/businesses/${id}/verify${force ? "?force=true" : ""}`, {
      method: "POST",
    });
  }

  async reEnrichBusiness(id: string): Promise<SingleResponse<{ reEnriched: true }>> {
    return this.request(`/businesses/${id}/re-enrich`, { method: "POST" });
  }

  async getBusinessWebsite(id: string): Promise<SingleResponse<Website | null>> {
    return this.request<SingleResponse<Website | null>>(`/businesses/${id}/website`);
  }

  async listBusinessContacts(id: string): Promise<SingleResponse<Contact[]>> {
    return this.request<SingleResponse<Contact[]>>(`/businesses/${id}/contacts`);
  }

  async addBusinessContact(
    id: string,
    type: Contact["type"],
    value: string,
  ): Promise<SingleResponse<Contact>> {
    return this.request(`/businesses/${id}/contacts`, {
      method: "POST",
      body: JSON.stringify({ type, value }),
    });
  }

  async listBusinessSocialProfiles(
    id: string,
  ): Promise<SingleResponse<SocialProfile[]>> {
    return this.request<SingleResponse<SocialProfile[]>>(
      `/businesses/${id}/social-profiles`,
    );
  }

  // ── Social Profiles (global) ───────────────────────────────────────────

  async listSocialProfiles(
    filters: SocialProfileListFilters = {},
  ): Promise<PaginatedResponse<SocialProfileWithBusiness>> {
    const params = new URLSearchParams();
    const entries: Array<[string, unknown]> = [
      ["page", filters.page ?? 1],
      ["limit", filters.limit ?? 50],
      ["platform", filters.platform],
      ["q", filters.q],
      ["min_followers", filters.min_followers],
      ["sort_by", filters.sort_by ?? "followers"],
      ["sort_dir", filters.sort_dir ?? "desc"],
    ];
    for (const [key, value] of entries) {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    }
    return this.request<PaginatedResponse<SocialProfileWithBusiness>>(
      `/social-profiles?${params.toString()}`,
    );
  }

  // ── Leads ───────────────────────────────────────────────────────────────

  async listLeads(
    filters: LeadListFilters = {},
  ): Promise<PaginatedResponse<Lead>> {
    const params = new URLSearchParams();
    const entries: Array<[string, unknown]> = [
      ["page", filters.page ?? 1],
      ["limit", filters.limit ?? 50],
      ["score_min", filters.score_min],
      ["score_max", filters.score_max],
      ["grade", filters.grade],
      ["website_status", filters.website_status],
      ["best_contact_method", filters.best_contact_method],
      ["city", filters.city],
      ["country", filters.country],
      ["verified_email", filters.verified_email ? "true" : undefined],
      ["has_mobile", filters.has_mobile ? "true" : undefined],
      ["include_stats", filters.include_stats ? "true" : undefined],
    ];
    for (const [key, value] of entries) {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    }
    return this.request<PaginatedResponse<Lead>>(`/leads?${params.toString()}`);
  }

  async getLead(businessId: string): Promise<SingleResponse<Lead>> {
    return this.request<SingleResponse<Lead>>(`/leads/${businessId}`);
  }

  // ── Bulk Actions ────────────────────────────────────────────────────────

  async bulkReEnrich(businessIds: string[]): Promise<SingleResponse<{ queued: number }>> {
    const results = await Promise.allSettled(
      businessIds.map((id) => this.reEnrichBusiness(id)),
    );
    const queued = results.filter((r) => r.status === "fulfilled").length;
    return { success: true, data: { queued } };
  }

  // ── Analytics ───────────────────────────────────────────────────────────

  async dashboardStats(): Promise<SingleResponse<DashboardStats>> {
    return this.request<SingleResponse<DashboardStats>>(`/analytics/dashboard`);
  }

  async leadDistribution(): Promise<
    SingleResponse<{ distribution: GradeDistribution }>
  > {
    return this.request<SingleResponse<{ distribution: GradeDistribution }>>(
      `/analytics/lead-distribution`,
    );
  }

  // ── Exports ─────────────────────────────────────────────────────────────

  async createExport(payload: {
    format: ExportFormat;
    filters?: ExportFilters;
  }): Promise<SingleResponse<{ export_id: string }>> {
    return this.request(`/exports`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getSearchJobProgress(
    id: string,
  ): Promise<SingleResponse<SearchJobProgress>> {
    return this.request<SingleResponse<SearchJobProgress>>(
      `/search-jobs/${id}/progress`,
    );
  }

  async getEngineActivity(limit = 25): Promise<SingleResponse<EngineActivity>> {
    return this.request<SingleResponse<EngineActivity>>(
      `/jobs/activity?recent_limit=${limit}`,
    );
  }

  async getVerificationCapabilities(): Promise<
    SingleResponse<VerificationCapabilities>
  > {
    return this.request<SingleResponse<VerificationCapabilities>>(
      `/verification/capabilities`,
    );
  }

  async bulkVerifyBusinesses(
    businessIds: string[],
    force = false,
  ): Promise<SingleResponse<{ queued: number }>> {
    return this.request(`/businesses/verify`, {
      method: "POST",
      body: JSON.stringify({ business_ids: businessIds, force }),
    });
  }

  async listSuppressions(): Promise<SingleResponse<Suppression[]>> {
    return this.request<SingleResponse<Suppression[]>>(`/suppressions`);
  }

  async addSuppression(payload: {
    kind: Suppression["kind"];
    value: string;
    reason?: string;
    note?: string;
  }): Promise<SingleResponse<Suppression>> {
    return this.request(`/suppressions`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async bulkAddSuppressions(
    entries: Array<Pick<Suppression, "kind" | "value"> & { reason?: string }>,
  ): Promise<SingleResponse<{ added: number; skipped: number }>> {
    return this.request(`/suppressions/bulk`, {
      method: "POST",
      body: JSON.stringify({ entries }),
    });
  }

  async deleteSuppression(id: string): Promise<SingleResponse<{ deleted: true }>> {
    return this.request(`/suppressions/${id}`, { method: "DELETE" });
  }

  async listExports(): Promise<SingleResponse<ExportRecord[]>> {
    return this.request<SingleResponse<ExportRecord[]>>(`/exports`);
  }

  getExportDownloadUrl(id: string): string {
    return `${API_BASE}/exports/${id}/download`;
  }

  // ── Admin ───────────────────────────────────────────────────────────────

  async queueStats(): Promise<SingleResponse<{ stats: Record<string, QueueStats> }>> {
    return this.request(`/admin/queues`);
  }

  async retryFailedJobs(): Promise<SingleResponse<{ retried: number }>> {
    return this.request(`/admin/queues/retry`, { method: "POST" });
  }
}

export interface QueueStats {
  waiting: number;
  in_progress: number;
  complete: number;
  failed: number;
}

export const api = new ApiClient();