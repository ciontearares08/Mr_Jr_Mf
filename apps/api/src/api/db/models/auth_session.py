import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base
from api.db.models.user import User


class AuthSession(Base):
    """One signed-in device. Deleting the row signs that device out."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 of the refresh token the device holds now. Each refresh replaces it.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # The token it replaced, accepted for a few seconds when two tabs refresh at once.
    previous_refresh_token_hash: Mapped[str | None] = mapped_column(String(64))
    refreshed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped[User] = relationship()
