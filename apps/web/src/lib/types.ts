// Types matching backend response shape

export type SearchJobStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type WebsiteStatus = "UNKNOWN" | "FOUND" | "NOT_FOUND" | "INVALID";

export type ContactType =
  | "EMAIL"
  | "PHONE"
  | "WHATSAPP"
  | "CONTACT_FORM"
  | "FACEBOOK"
  | "INSTAGRAM"
  | "LINKEDIN"
  | "YOUTUBE"
  | "TIKTOK"
  | "TWITTER";

export type VerificationStatus =
  | "UNVERIFIED"
  | "VALID"
  | "RISKY"
  | "CATCH_ALL"
  | "INVALID"
  | "UNKNOWN";

export type PhoneLineType =
  | "MOBILE"
  | "LANDLINE"
  | "VOIP"
  | "TOLL_FREE"
  | "UNKNOWN";

export interface ContactVerification {
  status: VerificationStatus;
  confidence: number;
  reason: string | null;
  method: string | null;
  checked_at: string | null;
  line_type: PhoneLineType | null;
}

export type ContactSource =
  | "MAPS"
  | "WEBSITE"
  | "SOCIAL"
  | "DIRECTORY"
  | "MANUAL";

export type SocialPlatform =
  | "FACEBOOK"
  | "INSTAGRAM"
  | "LINKEDIN"
  | "YOUTUBE"
  | "TIKTOK"
  | "TWITTER";

export type LeadGrade = "A+" | "A" | "B" | "C" | "D" | "F";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: "USER" | "ADMIN";
  created_at: string;
}

export interface AuthSuccess {
  user: User;
  token: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  full_name?: string;
}

export interface SearchJob {
  id: string;
  user_id: string;
  keyword: string;
  location: string;
  radius_km: number | null;
  country: string | null;
  status: SearchJobStatus;
  total_discovered: number;
  total_enriched: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Business {
  id: string;
  external_id: string | null;
  name: string;
  category: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  phone: string | null;
  rating: number | null;
  review_count: number | null;
  source: string | null;
  website_status: WebsiteStatus;
  is_claimed: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface Website {
  id: string;
  business_id: string;
  url: string;
  domain: string | null;
  ssl_enabled: boolean | null;
  is_reachable: boolean | null;
  http_status: number | null;
  load_time_ms: number | null;
  mobile_friendly: boolean | null;
  seo_score: number | null;
  last_checked_at: string | null;
}

export interface Contact {
  id: string;
  business_id: string;
  type: ContactType;
  value: string;
  source: ContactSource;
  confidence_score: number;
  is_verified: boolean;
  verification?: ContactVerification | null;
  created_at: string;
}

export interface SocialProfile {
  id: string;
  business_id: string;
  platform: SocialPlatform;
  profile_url: string;
  username: string | null;
  followers: number | null;
  following: number | null;
  posts_count: number | null;
  bio: string | null;
  website: string | null;
  public_email: string | null;
  public_phone: string | null;
  last_activity_at: string | null;
}

export interface SocialProfileWithBusiness extends SocialProfile {
  created_at: string;
  business_name: string | null;
  business_city: string | null;
}

export interface SocialProfileListFilters {
  page?: number;
  limit?: number;
  platform?: SocialPlatform;
  q?: string;
  min_followers?: number;
  sort_by?: "followers" | "posts_count" | "created_at";
  sort_dir?: "asc" | "desc";
}

export interface SearchJobWithBusinesses extends SearchJob {
  businesses?: Array<{
    id: string;
    business: Business;
  }>;
}

export interface LeadScore {
  id: string;
  business_id: string;
  score: number;
  grade: LeadGrade | null;
  best_contact_method: string | null;
  website_opportunity_score: number;
  social_activity_score: number;
  contact_quality_score: number;
  review_score: number;
  business_validation_score: number;
  notes: string | null;
  calculated_at: string;
}

export interface ProvenanceRow {
  field: string;
  value: string;
  source: string;
  source_url: string | null;
  confidence: number;
  first_seen_at: string;
  last_checked_at: string;
}

export interface Lead {
  business: Business;
  lead_score: LeadScore | null;
  contacts: Contact[];
  social_profiles: SocialProfile[];
  website: Website | null;
  provenance?: ProvenanceRow[];
}

export type ScheduleCadence = "DAILY" | "WEEKLY" | "MONTHLY";

export interface SearchSchedule {
  id: string;
  keyword: string;
  location: string;
  country: string | null;
  radius_km: number | null;
  cadence: ScheduleCadence;
  hour: number;
  minute: number;
  weekday: number | null;
  day_of_month: number | null;
  timezone: string;
  enabled: boolean;
  next_run_at: string;
  last_run_at: string | null;
  last_job_id: string | null;
  created_at: string;
}

export interface ScheduleRun {
  job_id: string;
  status: SearchJobStatus;
  keyword: string;
  location: string;
  total_discovered: number;
  total_enriched: number;
  created_at: string;
}

export interface SearchJobProgress {
  job_id: string;
  status: SearchJobStatus;
  keyword: string;
  location: string;
  total_discovered: number;
  total_enriched: number;
  percent: number;
  stages: {
    website: number;
    contacts: number;
    socials: number;
    verified: number;
    checked: number;
    scored: number;
  };
}

export interface EngineRun {
  id: string;
  business_id: string;
  business_name: string | null;
  worker: string;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
  job_id: string | null;
}

export interface EngineActivity {
  active: EngineRun[];
  recent: EngineRun[];
  queues: Record<string, number>;
  counts: { active: number; waiting: number };
}

export interface VerificationCapabilities {
  provider: string;
  supports_valid: boolean;
  supports_domain_checked: boolean;
  max_age_days: number;
}

export interface Suppression {
  id: string;
  kind: "EMAIL" | "PHONE" | "DOMAIN";
  value: string;
  reason: string;
  note: string | null;
  created_at: string;
}

export interface DashboardStats {
  businesses: number;
  websitesFound: number;
  emailsFound: number;
  socialProfilesFound: number;
  highValueLeads: number;
}

export type GradeDistribution = Record<LeadGrade, number>;

export type ExportFormat = "CSV" | "JSON" | "XLSX";

export type ExportStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED";

export interface ExportFilters {
  search_job_id?: string;
  grade?: LeadGrade;
  score_min?: number;
  score_max?: number;
  best_contact_method?: ContactType;
  city?: string;
  country?: string;
  website_status?: WebsiteStatus;
  verified_email_only?: boolean;
}

export interface ExportRecord {
  id: string;
  user_id: string;
  format: ExportFormat;
  file_path: string | null;
  total_records: number;
  status: ExportStatus;
  created_at: string;
}

export interface LeadListFilters {
  page?: number;
  limit?: number;
  score_min?: number;
  score_max?: number;
  grade?: LeadGrade;
  website_status?: WebsiteStatus;
  best_contact_method?: string;
  city?: string;
  country?: string;
  verified_email?: boolean;
  has_mobile?: boolean;
  include_stats?: boolean;
}

export interface BusinessListFilters {
  page?: number;
  limit?: number;
  name?: string;
  city?: string;
  country?: string;
  category?: string;
  website_status?: WebsiteStatus;
  min_rating?: number;
  max_rating?: number;
}

export interface PaginatedResponse<T> {
  success: true;
  data: T[];
  meta: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
    total_count?: number;
    verified_email_count?: number;
    checked_email_count?: number;
    mobile_count?: number;
  };
}

export interface SingleResponse<T> {
  success: true;
  data: T;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    context?: Record<string, unknown>;
  };
}