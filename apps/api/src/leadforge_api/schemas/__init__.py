"""Pydantic request/response schemas for all endpoints. 1:1 with TS API_SPEC.md."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from leadforge_shared.types import (
    ContactSource,
    ContactType,
    ExportFilters,
    ExportFormat,
    LeadGrade,
    SearchJobStatus,
    SocialPlatform,
    UserRole,
    WebsiteStatus,
)
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

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


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    type: ContactType
    value: str
    source: ContactSource
    confidence_score: int
    is_verified: bool
    created_at: datetime


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
