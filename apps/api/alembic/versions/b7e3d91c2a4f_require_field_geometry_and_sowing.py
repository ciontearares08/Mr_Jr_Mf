"""require field geometry and sowing

Revision ID: b7e3d91c2a4f
Revises: ca554da8bf9b
Create Date: 2026-11-09 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e3d91c2a4f"
down_revision: str | Sequence[str] | None = "ca554da8bf9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOWING_CONSTRAINT = "ck_fields_sowing_date_or_window"
# A sowing date or a whole sowing window, never both and never none.
SOWING_CONDITION = (
    "(sowing_date IS NOT NULL"
    " AND sowing_window_start IS NULL AND sowing_window_end IS NULL)"
    " OR (sowing_date IS NULL"
    " AND sowing_window_start IS NOT NULL AND sowing_window_end IS NOT NULL"
    " AND sowing_window_start <= sowing_window_end)"
)


def upgrade() -> None:
    """Upgrade schema."""
    # Fields from before S3-01 can have no boundary or no sowing data. The
    # system has no users yet, so we delete those rows instead of guessing.
    op.execute(f"DELETE FROM fields WHERE geom IS NULL OR NOT ({SOWING_CONDITION})")
    op.alter_column("fields", "geom", nullable=False)
    op.create_check_constraint(SOWING_CONSTRAINT, "fields", SOWING_CONDITION)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(SOWING_CONSTRAINT, "fields", type_="check")
    op.alter_column("fields", "geom", nullable=True)
