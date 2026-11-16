"""integrations (hubspot, sheets)

Revision ID: 6c1d9a3e5b20
Revises: 2b8f6c4d9e71
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6c1d9a3e5b20"
down_revision: str | None = "2b8f6c4d9e71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN CREATE TYPE integration_kind AS ENUM ('HUBSPOT','SHEETS'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.create_table(
        "integrations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("HUBSPOT", "SHEETS", name="integration_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("config_encrypted", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("user_id", "kind", name="uq_integrations_user_kind"),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
    op.execute("DROP TYPE integration_kind")
