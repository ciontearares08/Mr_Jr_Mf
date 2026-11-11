"""merge weather daily and field requirements

Revision ID: d41a7c9e3b52
Revises: 6f9030ce0fec, b7e3d91c2a4f
Create Date: 2026-11-11 12:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d41a7c9e3b52"
down_revision: str | Sequence[str] | None = ("6f9030ce0fec", "b7e3d91c2a4f")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
