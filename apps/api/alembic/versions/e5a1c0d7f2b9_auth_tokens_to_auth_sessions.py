"""turn auth tokens into auth sessions with refresh tokens

Revision ID: e5a1c0d7f2b9
Revises: d41a7c9e3b52
Create Date: 2026-11-13 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a1c0d7f2b9"
down_revision: str | Sequence[str] | None = "d41a7c9e3b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Old tokens have no refresh token, so everyone signs in again.
    op.execute("DELETE FROM auth_tokens")
    op.rename_table("auth_tokens", "auth_sessions")
    op.execute(
        "ALTER TABLE auth_sessions RENAME CONSTRAINT auth_tokens_pkey TO auth_sessions_pkey"
    )
    op.execute(
        "ALTER TABLE auth_sessions RENAME CONSTRAINT auth_tokens_user_id_fkey "
        "TO auth_sessions_user_id_fkey"
    )
    op.execute("ALTER INDEX ix_auth_tokens_user_id RENAME TO ix_auth_sessions_user_id")
    op.add_column(
        "auth_sessions",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("previous_refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("auth_sessions", "refreshed_at")
    op.drop_column("auth_sessions", "previous_refresh_token_hash")
    op.drop_column("auth_sessions", "refresh_token_hash")
    op.execute("ALTER INDEX ix_auth_sessions_user_id RENAME TO ix_auth_tokens_user_id")
    op.execute(
        "ALTER TABLE auth_sessions RENAME CONSTRAINT auth_sessions_user_id_fkey "
        "TO auth_tokens_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE auth_sessions RENAME CONSTRAINT auth_sessions_pkey TO auth_tokens_pkey"
    )
    op.rename_table("auth_sessions", "auth_tokens")
