"""scheduled searches

Revision ID: 7d4e2c9a1f60
Revises: 9f2c1a7b4d31
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7d4e2c9a1f60"
down_revision: str | None = "9f2c1a7b4d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE schedule_cadence AS ENUM ('DAILY','WEEKLY','MONTHLY'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.create_table(
        "search_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("radius_km", sa.Integer(), nullable=True),
        sa.Column(
            "cadence",
            postgresql.ENUM(
                "DAILY", "WEEKLY", "MONTHLY", name="schedule_cadence", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_schedules_user_id", "search_schedules", ["user_id"])
    op.create_index("ix_search_schedules_due", "search_schedules", ["enabled", "next_run_at"])

    op.add_column("search_jobs", sa.Column("schedule_id", sa.UUID(), nullable=True))
    op.create_index("ix_search_jobs_schedule_id", "search_jobs", ["schedule_id"])
    op.create_foreign_key(
        "fk_search_jobs_schedule_id",
        "search_jobs",
        "search_schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_search_jobs_schedule_id", "search_jobs", type_="foreignkey")
    op.drop_index("ix_search_jobs_schedule_id", table_name="search_jobs")
    op.drop_column("search_jobs", "schedule_id")

    op.drop_index("ix_search_schedules_due", table_name="search_schedules")
    op.drop_index("ix_search_schedules_user_id", table_name="search_schedules")
    op.drop_table("search_schedules")
    op.execute("DROP TYPE schedule_cadence")
