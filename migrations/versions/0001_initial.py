"""Versioned local document store, with indexed record kinds."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
    )
    op.create_index("ix_records_kind", "records", ["kind"])


def downgrade():
    op.drop_index("ix_records_kind", "records")
    op.drop_table("records")
