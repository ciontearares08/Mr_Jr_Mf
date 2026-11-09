"""add field wind station

Revision ID: ca554da8bf9b
Revises: 4eb962b3fa49
Create Date: 2026-11-09 09:22:29.109839

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ca554da8bf9b"
down_revision: str | Sequence[str] | None = "4eb962b3fa49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "fields", sa.Column("wind_station_id", sa.String(length=10), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("fields", "wind_station_id")
