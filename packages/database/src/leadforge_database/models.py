"""SQLAlchemy 2.0 async ORM models. 1:1 with packages/database/prisma/schema.prisma."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from leadforge_shared.types import (
    ContactSource,
    ContactType,
    EnrichmentStatus,
    ExportFormat,
    PhoneLineType,
    ScheduleCadence,
    SearchJobStatus,
    SocialPlatform,
    SuppressionKind,
    UserRole,
    VerificationStatus,
    WebsiteStatus,
)
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    pass


_UUID = PG_UUID(as_uuid=True)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(_UUID, primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    search_jobs: Mapped[list[SearchJob]] = relationship(back_populates="user")
    exports: Mapped[list[Export]] = relationship(back_populates="user")

    __table_args__ = (Index("ix_users_email", "email"),)


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(_UUID, ForeignKey("users.id"), nullable=False)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        _UUID, ForeignKey("search_schedules.id", ondelete="SET NULL"), nullable=True
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    radius_km: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[SearchJobStatus] = mapped_column(
        SAEnum(
            SearchJobStatus,
            name="search_job_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SearchJobStatus.PENDING,
        nullable=False,
    )
    total_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_enriched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()

    user: Mapped[User] = relationship(back_populates="search_jobs")
    businesses: Mapped[list[SearchJobBusiness]] = relationship(back_populates="search_job")

    __table_args__ = (
        Index("ix_search_jobs_user_id", "user_id"),
        Index("ix_search_jobs_schedule_id", "schedule_id"),
        Index("ix_search_jobs_status", "status"),
        Index("ix_search_jobs_created_at", "created_at"),
    )


class SearchSchedule(Base):
    """Recurring search definition executed by the scheduler worker."""

    __tablename__ = "search_schedules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(_UUID, ForeignKey("users.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2))
    radius_km: Mapped[int | None] = mapped_column(Integer)
    cadence: Mapped[ScheduleCadence] = mapped_column(
        SAEnum(
            ScheduleCadence,
            name="schedule_cadence",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ScheduleCadence.WEEKLY,
        nullable=False,
    )
    hour: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weekday: Mapped[int | None] = mapped_column(Integer)
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_job_id: Mapped[uuid.UUID | None] = mapped_column(_UUID)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_search_schedules_user_id", "user_id"),
        Index("ix_search_schedules_due", "enabled", "next_run_at"),
    )


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(50))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(100))
    rating: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(50), default="GOOGLE_MAPS")
    website_status: Mapped[WebsiteStatus] = mapped_column(
        SAEnum(
            WebsiteStatus, name="website_status", values_callable=lambda e: [m.value for m in e]
        ),
        default=WebsiteStatus.UNKNOWN,
        nullable=False,
    )
    is_claimed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    search_jobs: Mapped[list[SearchJobBusiness]] = relationship(back_populates="business")
    website: Mapped[Website | None] = relationship(back_populates="business", uselist=False)
    contacts: Mapped[list[Contact]] = relationship(back_populates="business")
    social_profiles: Mapped[list[SocialProfile]] = relationship(back_populates="business")
    lead_score: Mapped[LeadScore | None] = relationship(back_populates="business", uselist=False)
    enrichment_runs: Mapped[list[EnrichmentRun]] = relationship(back_populates="business")
    provenance: Mapped[list[FieldProvenance]] = relationship(back_populates="business")

    __table_args__ = (
        Index("ix_businesses_name", "name"),
        Index("ix_businesses_city", "city"),
        Index("ix_businesses_country", "country"),
        Index("ix_businesses_source", "source"),
        Index("ix_businesses_website_status", "website_status"),
    )


class SearchJobBusiness(Base):
    __tablename__ = "search_job_businesses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    search_job_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("search_jobs.id"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), nullable=False
    )
    created_at: Mapped[datetime] = _now()

    search_job: Mapped[SearchJob] = relationship(back_populates="businesses")
    business: Mapped[Business] = relationship(back_populates="search_jobs")

    __table_args__ = (
        Index("ix_search_job_businesses_search_job_id", "search_job_id"),
        Index("ix_search_job_businesses_business_id", "business_id"),
    )


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), unique=True, nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    ssl_enabled: Mapped[bool | None] = mapped_column(Boolean)
    is_reachable: Mapped[bool | None] = mapped_column(Boolean)
    http_status: Mapped[int | None] = mapped_column(Integer)
    load_time_ms: Mapped[int | None] = mapped_column(Integer)
    mobile_friendly: Mapped[bool | None] = mapped_column(Boolean)
    seo_score: Mapped[int | None] = mapped_column(Integer)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    business: Mapped[Business] = relationship(back_populates="website")

    __table_args__ = (
        Index("ix_websites_domain", "domain"),
        Index("ix_websites_business_id", "business_id"),
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), nullable=False
    )
    type: Mapped[ContactType] = mapped_column(
        SAEnum(ContactType, name="contact_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[ContactSource] = mapped_column(
        SAEnum(
            ContactSource, name="contact_source", values_callable=lambda e: [m.value for m in e]
        ),
        default=ContactSource.WEBSITE,
        nullable=False,
    )
    confidence_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(
            VerificationStatus,
            name="verification_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=VerificationStatus.UNVERIFIED,
        server_default=VerificationStatus.UNVERIFIED.value,
        nullable=False,
    )
    verification_confidence: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    verification_reason: Mapped[str | None] = mapped_column(Text)
    verification_method: Mapped[str | None] = mapped_column(String(32))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    line_type: Mapped[PhoneLineType | None] = mapped_column(
        SAEnum(
            PhoneLineType, name="phone_line_type", values_callable=lambda e: [m.value for m in e]
        )
    )
    created_at: Mapped[datetime] = _now()

    business: Mapped[Business] = relationship(back_populates="contacts")

    @property
    def verification(self) -> dict[str, object] | None:
        """Nested verification payload consumed by the API schema."""
        if self.verification_status == VerificationStatus.UNVERIFIED and self.verified_at is None:
            return None
        return {
            "status": self.verification_status,
            "confidence": self.verification_confidence,
            "reason": self.verification_reason,
            "method": self.verification_method,
            "checked_at": self.verified_at,
            "line_type": self.line_type,
        }

    __table_args__ = (
        Index("ix_contacts_business_id", "business_id"),
        Index("ix_contacts_type", "type"),
        Index("ix_contacts_value", "value"),
        Index("ix_contacts_business_type_status", "business_id", "type", "verification_status"),
        Index("ix_contacts_verified_at", "verified_at"),
    )


class FieldProvenance(Base):
    """Where a business field came from, when it was first seen, when last checked."""

    __tablename__ = "field_provenance"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    first_seen_at: Mapped[datetime] = _now()
    last_checked_at: Mapped[datetime] = _now()
    enrichment_run_id: Mapped[uuid.UUID | None] = mapped_column(
        _UUID, ForeignKey("enrichment_runs.id")
    )

    business: Mapped[Business] = relationship(back_populates="provenance")

    __table_args__ = (
        UniqueConstraint(
            "business_id", "field", "value", name="uq_field_provenance_business_field_value"
        ),
        Index("ix_field_provenance_business_id", "business_id"),
        Index("ix_field_provenance_field", "field"),
    )


class Suppression(Base):
    """Workspace-scoped do-not-contact entries enforced on export."""

    __tablename__ = "suppressions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(_UUID, ForeignKey("users.id"), nullable=False)
    kind: Mapped[SuppressionKind] = mapped_column(
        SAEnum(
            SuppressionKind,
            name="suppression_kind",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        UniqueConstraint("user_id", "kind", "value", name="uq_suppressions_user_kind_value"),
        Index("ix_suppressions_user_id", "user_id"),
        Index("ix_suppressions_value", "value"),
    )


class SocialProfile(Base):
    __tablename__ = "social_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), nullable=False
    )
    platform: Mapped[SocialPlatform] = mapped_column(
        SAEnum(
            SocialPlatform, name="social_platform", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    profile_url: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    followers: Mapped[int | None] = mapped_column(Integer)
    following: Mapped[int | None] = mapped_column(Integer)
    posts_count: Mapped[int | None] = mapped_column(Integer)
    bio: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    public_email: Mapped[str | None] = mapped_column(Text)
    public_phone: Mapped[str | None] = mapped_column(Text)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    business: Mapped[Business] = relationship(back_populates="social_profiles")

    __table_args__ = (
        UniqueConstraint("platform", "profile_url", name="uq_social_profiles_platform_url"),
        Index("ix_social_profiles_business_id", "business_id"),
        Index("ix_social_profiles_platform", "platform"),
        Index("ix_social_profiles_username", "username"),
    )


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), unique=True, nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grade: Mapped[str | None] = mapped_column(String(5))
    best_contact_method: Mapped[str | None] = mapped_column(String(100))
    website_opportunity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    social_activity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contact_quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    business_validation_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    calculated_at: Mapped[datetime] = _now()
    created_at: Mapped[datetime] = _now()

    business: Mapped[Business] = relationship(back_populates="lead_score")

    __table_args__ = (
        Index("ix_lead_scores_score", "score"),
        Index("ix_lead_scores_grade", "grade"),
        Index("ix_lead_scores_best_contact_method", "best_contact_method"),
    )


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id"), nullable=False
    )
    worker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[EnrichmentStatus] = mapped_column(
        SAEnum(
            EnrichmentStatus,
            name="enrichment_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=EnrichmentStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = _now()

    business: Mapped[Business] = relationship(back_populates="enrichment_runs")

    __table_args__ = (
        Index("ix_enrichment_runs_business_id", "business_id"),
        Index("ix_enrichment_runs_worker_name", "worker_name"),
        Index("ix_enrichment_runs_status", "status"),
    )


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(_UUID, ForeignKey("users.id"), nullable=False)
    format: Mapped[ExportFormat] = mapped_column(
        SAEnum(ExportFormat, name="export_format", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(Text)
    filters: Mapped[dict | None] = mapped_column(JSONB, default=None)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = _now()

    user: Mapped[User] = relationship(back_populates="exports")

    __table_args__ = (
        Index("ix_exports_user_id", "user_id"),
        Index("ix_exports_status", "status"),
    )


class JobQueueLog(Base):
    __tablename__ = "job_queue_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False)
    worker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        Index("ix_job_queue_logs_queue_name", "queue_name"),
        Index("ix_job_queue_logs_status", "status"),
        Index("ix_job_queue_logs_created_at", "created_at"),
    )
