"""Pydantic request/response schemas for all endpoints. 1:1 with TS API_SPEC.md."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from leadforge_shared.types import (
    ContactSource,
    ContactType,
    ExportFilters,
    ExportFormat,
    LeadGrade,
    PhoneLineType,
    ScheduleCadence,
    SearchJobStatus,
    SocialPlatform,
    SuppressionKind,
    UserRole,
    VerificationStatus,
    WebsiteStatus,
)
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

# ---------- Auth ----------


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(
        default=None, validation_alias=AliasChoices("fullName", "full_name")
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: UserRole
    created_at: datetime


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: UserResponse
    token: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    user: UserResponse


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(
        default=None, validation_alias=AliasChoices("fullName", "full_name")
    )
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


# ---------- Search Jobs ----------


class CreateSearchJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keyword: str = Field(min_length=1)
    location: str = Field(min_length=1)
    radius_km: int | None = Field(default=None, gt=0)
    country: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="ISO-3166-1 alpha-2 country code (e.g. US, GB, PK). Auto-detected if omitted.",
    )


class CreateSearchJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID
    status: SearchJobStatus


class SearchJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    keyword: str
    location: str
    radius_km: int | None
    status: SearchJobStatus
    total_discovered: int
    total_enriched: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


# ---------- Business ----------


class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    external_id: str | None
    name: str
    category: str | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    rating: float | None
    review_count: int | None
    source: str | None
    website_status: WebsiteStatus
    is_claimed: bool | None
    created_at: datetime
    updated_at: datetime


class WebsiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    url: str
    domain: str | None
    ssl_enabled: bool | None
    is_reachable: bool | None
    http_status: int | None
    load_time_ms: int | None
    mobile_friendly: bool | None
    seo_score: int | None
    last_checked_at: datetime | None


class ContactVerificationResponse(BaseModel):
    status: VerificationStatus
    confidence: int
    reason: str | None
    method: str | None
    checked_at: datetime | None
    line_type: PhoneLineType | None


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    type: ContactType
    value: str
    source: ContactSource
    confidence_score: int
    is_verified: bool
    verification: ContactVerificationResponse | None = None
    created_at: datetime


class ProvenanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field: str
    value: str
    source: str
    source_url: str | None
    confidence: int
    first_seen_at: datetime
    last_checked_at: datetime


class AddContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: ContactType
    value: str


class SocialProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    platform: SocialPlatform
    profile_url: str
    username: str | None
    followers: int | None
    following: int | None
    posts_count: int | None
    bio: str | None
    website: str | None
    public_email: str | None
    public_phone: str | None
    last_activity_at: datetime | None


class SocialProfileWithBusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    platform: SocialPlatform
    profile_url: str
    username: str | None
    followers: int | None
    following: int | None
    posts_count: int | None
    bio: str | None
    website: str | None
    public_email: str | None
    public_phone: str | None
    last_activity_at: datetime | None
    created_at: datetime
    business_name: str | None = None
    business_city: str | None = None


class LeadScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    score: int
    grade: LeadGrade | None
    best_contact_method: str | None
    website_opportunity_score: int
    social_activity_score: int
    contact_quality_score: int
    review_score: int
    business_validation_score: int
    notes: str | None
    calculated_at: datetime


# ---------- Leads ----------


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    business: BusinessResponse
    lead_score: LeadScoreResponse | None
    contacts: list[ContactResponse]
    social_profiles: list[SocialProfileResponse]
    website: WebsiteResponse | None
    provenance: list[ProvenanceResponse] = Field(default_factory=list)


# ---------- Schedules ----------


class ScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    radius_km: int | None = Field(default=None, gt=0)
    cadence: ScheduleCadence
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    timezone: str = "UTC"
    enabled: bool = True

    @model_validator(mode="after")
    def _validate(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        if self.cadence == ScheduleCadence.WEEKLY and self.weekday is None:
            raise ValueError("weekday is required for weekly schedules")
        return self


class ScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    radius_km: int | None = Field(default=None, gt=0)
    cadence: ScheduleCadence | None = None
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    weekday: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    timezone: str | None = None
    enabled: bool | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    keyword: str
    location: str
    country: str | None
    radius_km: int | None
    cadence: ScheduleCadence
    hour: int
    minute: int
    weekday: int | None
    day_of_month: int | None
    timezone: str
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None
    last_job_id: UUID | None
    created_at: datetime


class ScheduleRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID
    status: SearchJobStatus
    keyword: str
    location: str
    total_discovered: int
    total_enriched: int
    created_at: datetime


# ---------- Integrations ----------


class IntegrationUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any]
    enabled: bool = True


class IntegrationResponse(BaseModel):
    kind: str
    enabled: bool
    summary: str
    updated_at: datetime


class IntegrationTestResponse(BaseModel):
    ok: bool
    detail: str


class IntegrationPushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score_min: int | None = Field(default=None, ge=0, le=100)
    score_max: int | None = Field(default=None, ge=0, le=100)
    grade: str | None = None
    verified_email: bool = False
    limit: int = Field(default=100, ge=1, le=200)


class IntegrationPushResponse(BaseModel):
    pushed: int
    failed: int
    detail: str


# ---------- Webhooks ----------

WEBHOOK_EVENTS = (
    "search.completed",
    "export.completed",
    "verification.completed",
    "schedule.run",
)


class WebhookCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=12, max_length=2000)
    events: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_events(self):
        unknown = [event for event in self.events if event not in WEBHOOK_EVENTS]
        if unknown:
            raise ValueError(f"Unknown events: {', '.join(unknown)}")
        return self


class WebhookUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str | None = Field(default=None, min_length=12, max_length=2000)
    events: list[str] | None = Field(default=None, min_length=1)
    active: bool | None = None

    @model_validator(mode="after")
    def _check_events(self):
        if self.events is not None:
            unknown = [event for event in self.events if event not in WEBHOOK_EVENTS]
            if unknown:
                raise ValueError(f"Unknown events: {', '.join(unknown)}")
        return self


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    events: list[str]
    active: bool
    secret: str
    failure_count: int
    last_delivery_at: datetime | None
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event: str
    status: str
    attempts: int
    response_code: int | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class SuppressionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: SuppressionKind
    value: str = Field(min_length=1)
    reason: str = Field(default="manual", max_length=64)
    note: str | None = None


class SuppressionBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: list[SuppressionCreateRequest] = Field(min_length=1, max_length=1000)


class SuppressionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: SuppressionKind
    value: str
    reason: str
    note: str | None
    created_at: datetime


# ---------- Verification ----------


class BulkVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_ids: list[UUID] | None = Field(default=None, max_length=500)
    score_min: int | None = Field(default=None, ge=0, le=100)
    score_max: int | None = Field(default=None, ge=0, le=100)
    grade: str | None = None
    website_status: str | None = None
    best_contact_method: str | None = None
    city: str | None = None
    country: str | None = None
    verified_email: bool = False
    has_mobile: bool = False
    force: bool = False
    limit: int = Field(default=500, ge=1, le=500)


class BulkVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: int


# ---------- Exports ----------


class CreateExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: ExportFormat
    filters: ExportFilters | None = None


class CreateExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_id: UUID


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    format: ExportFormat
    file_path: str | None
    total_records: int
    status: str
    created_at: datetime


# ---------- Analytics ----------


class DashboardStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    businesses: int
    websites_found: int
    emails_found: int
    social_profiles_found: int
    high_value_leads: int


class LeadDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribution: dict[str, int]


# ---------- Admin / Queues ----------


class QueueStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stats: dict[str, dict[str, int]]
