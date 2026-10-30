"""add field geometry and sowing columns

Revision ID: 8f2dc107d319
Revises: 05b4fecc9d16
Create Date: 2026-10-30 07:56:01.581415

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "8f2dc107d319"
down_revision: str | Sequence[str] | None = "05b4fecc9d16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Written by hand: autogenerate turns a rename into drop + add and loses data.
    op.alter_column("fields", "area_hectares", new_column_name="area_ha")

    op.add_geospatial_column(
        "fields",
        sa.Column(
            "geom",
            Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False),
            nullable=True,
        ),
    )
    op.create_geospatial_index(
        "idx_fields_geom", "fields", ["geom"], unique=False, postgresql_using="gist"
    )

    op.add_column("fields", sa.Column("cell_id", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_fields_cell_id"), "fields", ["cell_id"], unique=False)
    op.add_column(
        "fields", sa.Column("soil_profile", sa.String(length=50), nullable=True)
    )
    op.add_column("fields", sa.Column("sowing_date", sa.Date(), nullable=True))
    op.add_column("fields", sa.Column("sowing_window_start", sa.Date(), nullable=True))
    op.add_column("fields", sa.Column("sowing_window_end", sa.Date(), nullable=True))
    op.add_column(
        "fields", sa.Column("recommended_sowing_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "fields",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("fields", "created_at")
    op.drop_column("fields", "recommended_sowing_date")
    op.drop_column("fields", "sowing_window_end")
    op.drop_column("fields", "sowing_window_start")
    op.drop_column("fields", "sowing_date")
    op.drop_column("fields", "soil_profile")
    op.drop_index(op.f("ix_fields_cell_id"), table_name="fields")
    op.drop_column("fields", "cell_id")
    op.drop_geospatial_index(
        "idx_fields_geom",
        table_name="fields",
        postgresql_using="gist",
        column_name="geom",
    )
    op.drop_geospatial_column("fields", "geom")
    op.alter_column("fields", "area_ha", new_column_name="area_hectares")
