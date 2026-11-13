"""Multi-tenant scoping helpers.

A business is visible to a user when it was discovered by one of that user's
search jobs (``search_jobs.user_id``). Every read path that returns business
data must apply this filter; otherwise any authenticated user can read every
other user's leads by guessing or listing IDs.
"""

from __future__ import annotations

from uuid import UUID

from leadforge_database.models import SearchJob, SearchJobBusiness
from sqlalchemy import Select, select


def user_business_ids(user_id: UUID) -> Select[tuple[UUID]]:
    """Scalar subquery: business IDs reachable through the user's search jobs."""
    return (
        select(SearchJobBusiness.business_id)
        .join(SearchJob, SearchJob.id == SearchJobBusiness.search_job_id)
        .where(SearchJob.user_id == user_id)
    )
