"""Isolated cloud accounts and revocable sessions; retain local records."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "records",
        sa.Column("owner_id", sa.String(), nullable=False, server_default="local"),
    )
    op.create_index("ix_records_owner_id", "records", ["owner_id"])
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("expires", sa.Float(), nullable=False),
    )
    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("at", sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table("auth_attempts")
    op.drop_table("sessions")
    op.drop_table("accounts")
    op.drop_index("ix_records_owner_id", "records")
    op.drop_column("records", "owner_id")
