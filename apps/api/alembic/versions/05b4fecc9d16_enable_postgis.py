"""enable postgis

Revision ID: 05b4fecc9d16
Revises: c6de6d262cde
Create Date: 2026-10-30 07:51:03.577728

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "05b4fecc9d16"
down_revision: str | Sequence[str] | None = "c6de6d262cde"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    """Downgrade schema."""
    # Intentionally empty: DROP EXTENSION postgis would drop every geometry column.
