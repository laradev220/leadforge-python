"""ScrapeState model for tracking pagination progress in long-running scrapers.

Allows resuming from the last successful page when a scrape fails mid-way,
preventing duplicate lead creation on retry (idempotency).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from leadforge_database.models import Base


class ScrapeStateStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScrapeState(Base):
    """Tracks the progress of long-running scraper jobs for idempotent retries.

    The job idempotency key is derived from: search_job_id + source + keyword + location.
    On retry, we resume from the last successful page rather than re-scraping from scratch.
    """

    __tablename__ = "scrape_states"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Which search job this scrape belongs to
    search_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("search_jobs.id"), nullable=True
    )
    # Source label (e.g. "google_maps", "yelp", "yellowpages_pk")
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    # Search parameters (for idempotency key)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    # Pagination state
    page_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_page_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Extracted external IDs so far (to detect duplicates on retry)
    extracted_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Note: Mapped[list] with JSONB works for reading/writing Python lists
    # because SQLAlchemy 2.0 serializes list to JSON automatically.
    # Status
    status: Mapped[ScrapeStateStatus] = mapped_column(
        SAEnum(ScrapeStateStatus, name="scrape_state_status", values_callable=lambda e: [m.value for m in e]),
        default=ScrapeStateStatus.IN_PROGRESS,
        nullable=False,
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Unique idempotency constraint
        Index(
            "ix_scrape_states_idempotency",
            "search_job_id", "source", "keyword", "location",
            unique=True,
        ),
        Index("ix_scrape_states_search_job_id", "search_job_id"),
        Index("ix_scrape_states_status", "status"),
    )

    def add_extracted_id(self, external_id: str) -> None:
        """Record an extracted external_id to prevent duplicates on retry."""
        if isinstance(self.extracted_ids, list):
            self.extracted_ids.append(external_id)

    def is_duplicate(self, external_id: str) -> bool:
        """Return True if this external_id was already extracted."""
        return external_id in (self.extracted_ids or [])

    def mark_completed(self) -> None:
        self.status = ScrapeStateStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def mark_failed(self) -> None:
        self.status = ScrapeStateStatus.FAILED
        self.completed_at = datetime.utcnow()