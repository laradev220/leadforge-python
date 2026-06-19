"""Types. Mirrors TS packages/shared/src/types.ts. Pydantic v2."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchJobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WebsiteStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"


class ContactType(str, Enum):
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


class ContactSource(str, Enum):
    MAPS = "MAPS"
    WEBSITE = "WEBSITE"
    SOCIAL = "SOCIAL"
    DIRECTORY = "DIRECTORY"
    MANUAL = "MANUAL"


class SocialPlatform(str, Enum):
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    LINKEDIN = "LINKEDIN"
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    TWITTER = "TWITTER"


class EnrichmentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExportFormat(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"


class LeadGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"


BusinessSource = Literal["GOOGLE_MAPS", "MANUAL", "DIRECTORY"]

QueueName = Literal[
    "discovery",
    "website",
    "contact",
    "social",
    "scoring",
    "export",
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


class ScoringJobData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_id: UUID


class ExportJobData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    export_id: UUID
    filters: dict[str, Any] | None = None


JobData = (
    DiscoveryJobData
    | WebsiteJobData
    | ContactJobData
    | SocialJobData
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
