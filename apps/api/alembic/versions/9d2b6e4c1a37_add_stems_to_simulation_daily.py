"""add stems to simulation daily

Revision ID: 9d2b6e4c1a37
Revises: 3c9e1f7a2b64
Create Date: 2026-11-24 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d2b6e4c1a37"
down_revision: str | Sequence[str] | None = "3c9e1f7a2b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("simulation_daily", sa.Column("stems", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("simulation_daily", "stems")
