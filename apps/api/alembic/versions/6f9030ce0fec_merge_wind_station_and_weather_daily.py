"""merge wind station and weather daily

Revision ID: 6f9030ce0fec
Revises: 7efbf14b8672, ca554da8bf9b
Create Date: 2026-11-10 15:52:17.065743

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '6f9030ce0fec'
down_revision: str | Sequence[str] | None = ('7efbf14b8672', 'ca554da8bf9b')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
