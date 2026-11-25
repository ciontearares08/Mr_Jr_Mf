"""add worker columns to simulation runs

Revision ID: 3c9e1f7a2b64
Revises: b8581f708cd8
Create Date: 2026-11-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3c9e1f7a2b64"
down_revision: str | Sequence[str] | None = "b8581f708cd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "simulation_runs",
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "simulation_runs",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "simulation_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "simulation_runs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The worker takes the oldest queued run, so index the status with the age
    op.create_index(
        "ix_simulation_runs_status_created_at",
        "simulation_runs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_simulation_runs_status_created_at", table_name="simulation_runs")
    op.drop_column("simulation_runs", "finished_at")
    op.drop_column("simulation_runs", "started_at")
    op.drop_column("simulation_runs", "attempts")
    op.drop_column("simulation_runs", "inputs")
