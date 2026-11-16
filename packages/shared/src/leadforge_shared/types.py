"""Types. Mirrors TS packages/shared/src/types.ts. Pydantic v2."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SearchJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WebsiteStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"


class ContactType(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    CONTACT_FORM = "CONTACT_FORM"
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    LINKEDIN = "LINKEDIN"
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    TWITTER = "TWITTER"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VALID = "VALID"
    RISKY = "RISKY"
    CATCH_ALL = "CATCH_ALL"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class PhoneLineType(StrEnum):
    MOBILE = "MOBILE"
    LANDLINE = "LANDLINE"
    VOIP = "VOIP"
    TOLL_FREE = "TOLL_FREE"
    UNKNOWN = "UNKNOWN"


class IntegrationKind(StrEnum):
    HUBSPOT = "HUBSPOT"
    SHEETS = "SHEETS"


class ScheduleCadence(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class SuppressionKind(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    DOMAIN = "DOMAIN"


class ContactSource(StrEnum):
    MAPS = "MAPS"
    WEBSITE = "WEBSITE"
    SOCIAL = "SOCIAL"
    DIRECTORY = "DIRECTORY"
    MANUAL = "MANUAL"


class SocialPlatform(StrEnum):
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    LINKEDIN = "LINKEDIN"
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    TWITTER = "TWITTER"


class EnrichmentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExportFormat(StrEnum):
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"


class ExportStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LeadGrade(StrEnum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


BusinessSource = Literal["GOOGLE_MAPS", "MANUAL", "DIRECTORY"]

QueueName = Literal[
    "discovery",
    "website",
    "contact",
    "social",
    "verification",
    "scoring",
    "export",
    "webhook",
]


class DiscoveryJobData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    search_job_id: UUID
    country: str | None = None


class WebsiteJobData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_id: UUID


class ContactJobData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_id: UUID
    website_url: str = ""


class SocialJobData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_id: UUID
    website_url: str = ""


class VerificationJobData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    business_id: UUID
    force: bool = False


class ScoringJobData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_id: UUID


class ExportFilters(BaseModel):
    """Validated export filter contract.

    Shared by the API (request validation) and the export worker so the two
    sides cannot disagree on field names. Unknown keys are rejected: a typo
    must fail loudly instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    search_job_id: UUID | None = None
    grade: LeadGrade | None = None
    score_min: int | None = Field(default=None, ge=0, le=100)
    score_max: int | None = Field(default=None, ge=0, le=100)
    best_contact_method: ContactType | None = None
    city: str | None = None
    country: str | None = None
    website_status: WebsiteStatus | None = None
    verified_email_only: bool = True

    @model_validator(mode="after")
    def _check_score_range(self) -> ExportFilters:
        if (
            self.score_min is not None
            and self.score_max is not None
            and self.score_min > self.score_max
        ):
            raise ValueError("score_min must be less than or equal to score_max")
        return self


class ExportJobData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    export_id: UUID
    filters: ExportFilters | None = None


JobData = (
    DiscoveryJobData
    | WebsiteJobData
    | ContactJobData
    | SocialJobData
    | VerificationJobData
    | ScoringJobData
    | ExportJobData
)


class WorkerLog(BaseModel):
    job_id: str
    worker: str
    business_id: UUID | None = None
    stage: str
    duration_ms: int
    status: Literal["success", "failure"]
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
