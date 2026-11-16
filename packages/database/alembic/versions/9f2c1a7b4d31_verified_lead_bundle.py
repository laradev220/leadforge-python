"""verified lead bundle: verification columns, provenance, suppressions

Revision ID: 9f2c1a7b4d31
Revises: 0b89b1a59740
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9f2c1a7b4d31"
down_revision: str | None = "0b89b1a59740"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VERIFICATION = postgresql.ENUM(
    "UNVERIFIED",
    "VALID",
    "RISKY",
    "CATCH_ALL",
    "INVALID",
    "UNKNOWN",
    name="verification_status",
    create_type=False,
)
_LINE_TYPE = postgresql.ENUM(
    "MOBILE",
    "LANDLINE",
    "VOIP",
    "TOLL_FREE",
    "UNKNOWN",
    name="phone_line_type",
    create_type=False,
)
_SUPPRESSION = postgresql.ENUM(
    "EMAIL",
    "PHONE",
    "DOMAIN",
    name="suppression_kind",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE verification_status AS ENUM "
        "('UNVERIFIED','VALID','RISKY','CATCH_ALL','INVALID','UNKNOWN')"
    )
    op.execute(
        "CREATE TYPE phone_line_type AS ENUM ('MOBILE','LANDLINE','VOIP','TOLL_FREE','UNKNOWN')"
    )
    op.execute("CREATE TYPE suppression_kind AS ENUM ('EMAIL','PHONE','DOMAIN')")

    op.add_column(
        "contacts",
        sa.Column(
            "verification_status",
            _VERIFICATION,
            server_default="UNVERIFIED",
            nullable=False,
        ),
    )
    op.add_column(
        "contacts",
        sa.Column("verification_confidence", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("contacts", sa.Column("verification_reason", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("verification_method", sa.String(32), nullable=True))
    op.add_column("contacts", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("line_type", _LINE_TYPE, nullable=True))

    op.create_index(
        "ix_contacts_business_type_status",
        "contacts",
        ["business_id", "type", "verification_status"],
        unique=False,
    )
    op.create_index("ix_contacts_verified_at", "contacts", ["verified_at"], unique=False)

    op.create_table(
        "field_provenance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), server_default="50", nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("enrichment_run_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["enrichment_run_id"], ["enrichment_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "field", "value", name="uq_field_provenance_business_field_value"
        ),
    )
    op.create_index(
        "ix_field_provenance_business_id", "field_provenance", ["business_id"], unique=False
    )
    op.create_index("ix_field_provenance_field", "field_provenance", ["field"], unique=False)

    op.create_table(
        "suppressions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", _SUPPRESSION, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(64), server_default="manual", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "kind", "value", name="uq_suppressions_user_kind_value"),
    )
    op.create_index("ix_suppressions_user_id", "suppressions", ["user_id"], unique=False)
    op.create_index("ix_suppressions_value", "suppressions", ["value"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_suppressions_value", table_name="suppressions")
    op.drop_index("ix_suppressions_user_id", table_name="suppressions")
    op.drop_table("suppressions")

    op.drop_index("ix_field_provenance_field", table_name="field_provenance")
    op.drop_index("ix_field_provenance_business_id", table_name="field_provenance")
    op.drop_table("field_provenance")

    op.drop_index("ix_contacts_verified_at", table_name="contacts")
    op.drop_index("ix_contacts_business_type_status", table_name="contacts")
    op.drop_column("contacts", "line_type")
    op.drop_column("contacts", "verified_at")
    op.drop_column("contacts", "verification_method")
    op.drop_column("contacts", "verification_reason")
    op.drop_column("contacts", "verification_confidence")
    op.drop_column("contacts", "verification_status")

    op.execute("DROP TYPE suppression_kind")
    op.execute("DROP TYPE phone_line_type")
    op.execute("DROP TYPE verification_status")
